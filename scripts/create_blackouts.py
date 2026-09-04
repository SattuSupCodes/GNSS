"""Generate GNSS-blackout evaluation datasets from calibrated trips.

Pipeline per scenario:
    1. Load the calibrated (or processed-fallback) trip frame.
    2. Plan outage interval(s) over real timestamps (deterministic via seed).
    3. Mask GNSS fields inside the outage(s); attach the offline vehicle
       reference when a synchronized reference file exists.
    4. Validate the hard invariants (GNSS NaN only inside, everything else
       byte-identical to the source) and write Parquet + scenario metadata
       under ``data/blackout``.

Scenarios that cannot be realized (trip too short, insufficient pre/post GNSS,
etc.) are reported with an explicit reason and skipped - never silently dropped.

Usage:
    python scripts/create_blackouts.py
    python scripts/create_blackouts.py --trip vw16b --duration 10 --duration 30
    python scripts/create_blackouts.py --seed 42 --n-scenarios 3 --limit 10
    python scripts/create_blackouts.py --duration 5 --trip s1 --random-seed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml
import pandas as pd

from src.data.blackout_validation import validate_blackout_frame
from src.data.dataset_manager import DatasetManager
from src.simulation.blackout_dataset import create_blackout_dataset
from src.simulation.blackout_scenarios import build_scenarios
from src.simulation.config import EvaluationConfig
from src.simulation.gnss_blackout import BlackoutImpossibleError


def load_yaml(name: str) -> dict:
    p = REPO_ROOT / "configs" / name
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_reference_frame(trip_id: str, ref_cfg) -> pd.DataFrame:
    """Load the synchronized vehicle reference for a trip, or None."""
    path = REPO_ROOT / ref_cfg.root / ref_cfg.file_pattern.format(trip_id=trip_id)
    if path.is_file():
        return pd.read_parquet(path)
    return None


def build_index(blackout_root: Path, output_cfg) -> list:
    """Rebuild the global scenarios index from the parquet files on disk."""
    index = []
    for p in sorted(blackout_root.rglob("*.parquet")):
        if p.stem.endswith("_vehicle_reference"):
            continue
        meta = p.with_name(f"{p.stem}_metadata.json")
        entry = {
            "scenario_id": p.stem,
            "file": str(p.relative_to(REPO_ROOT)),
            "metadata_file": (
                str(meta.relative_to(REPO_ROOT)) if meta.is_file() else None
            ),
        }
        if meta.is_file():
            entry.update(json.loads(meta.read_text(encoding="utf-8")))
        index.append(entry)
    return index


def parse_trips(value) -> list:
    trips = []
    for chunk in value or []:
        trips.extend(t.strip() for t in chunk.split(",") if t.strip())
    return trips


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trip", action="append", default=None, help="Trip id (repeatable / comma-separated)."
    )
    parser.add_argument(
        "--duration", action="append", type=float, default=None,
        help="Blackout duration in seconds (repeatable).",
    )
    parser.add_argument(
        "--n-intervals", type=int, default=None, help="Outages per scenario."
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="Deterministic generation seed."
    )
    parser.add_argument(
        "--n-scenarios", type=int, default=None,
        help="Independent scenarios per trip+duration.",
    )
    parser.add_argument(
        "--random-seed", action="store_true",
        help="Draw the seed from the OS RNG instead of the deterministic default.",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only the first N trips."
    )
    parser.add_argument(
        "--source", type=str, default=None,
        choices=["calibrated", "processed"], help="Input data source.",
    )
    parser.add_argument(
        "--config", type=str, default="evaluation_config.yaml", help="Config name."
    )
    args = parser.parse_args()

    eval_cfg = load_yaml(args.config) if args.config else {}
    cfg = EvaluationConfig.from_dict(eval_cfg)
    blackout_cfg = cfg.blackout
    output_cfg = cfg.output
    ref_cfg = cfg.reference

    if args.seed is not None:
        blackout_cfg.seed = args.seed
    if args.random_seed:
        import secrets

        blackout_cfg.seed = secrets.randbits(31)
    if args.n_scenarios is not None:
        blackout_cfg.n_scenarios_per_duration = args.n_scenarios
    if args.n_intervals is not None:
        blackout_cfg.n_intervals_per_scenario = args.n_intervals
    if args.source is not None:
        cfg.input.source = args.source

    durations = [float(d) for d in (args.duration or blackout_cfg.durations_s)]
    seed = int(blackout_cfg.seed)
    n_scen = int(blackout_cfg.n_scenarios_per_duration)
    n_int = int(blackout_cfg.n_intervals_per_scenario)

    data_cfg = load_yaml("data_config.yaml")["dataset"]
    manager = DatasetManager(
        str(REPO_ROOT / data_cfg["raw_root"]),
        str(REPO_ROOT / data_cfg["processed_root"]),
        str(REPO_ROOT / data_cfg["split_root"]),
    )

    trips = parse_trips(args.trip) or manager.calibrated_trips() or manager.list_trips()
    if args.limit:
        trips = trips[: args.limit]
    if not trips:
        print("No trips found. Run scripts/calibrate_dataset.py first.")
        return 1

    blackout_root = REPO_ROOT / output_cfg.root
    print(
        f"[generate] source={cfg.input.source} seed={seed} durations={durations} "
        f"scenarios/duration={n_scen} intervals={n_int}"
    )
    print(f"[generate] output root: {blackout_root}")

    summary = {"ok": 0, "skipped": []}
    made = []
    for trip_id in trips:
        try:
            frame = manager.load_calibrated_trip(trip_id)
            source_file = str(manager.calibrated_root / f"trip_{trip_id.lower()}.parquet")
        except FileNotFoundError:
            try:
                frame = manager.load_processed_trip(trip_id).data
            except FileNotFoundError:
                print(f"SKIP {trip_id}: unknown trip")
                continue
            source_file = None

        ts = pd.to_numeric(frame["timestamp"], errors="coerce").dropna()
        span = float(ts.max() - ts.min()) if len(ts) else 0.0
        if span < float(blackout_cfg.min_trip_duration_s):
            print(
                f"SKIP {trip_id}: trip spans {span:.1f}s < "
                f"min_trip_duration_s ({blackout_cfg.min_trip_duration_s:.1f}s)"
            )
            summary["skipped"].append(
                {"trip_id": trip_id, "reason": "trip_too_short", "span_s": span}
            )
            continue

        reference_df = (
            load_reference_frame(trip_id, ref_cfg)
            if ref_cfg.attach_vehicle_reference
            else None
        )
        for scenario in build_scenarios(
            [trip_id], durations, seed=seed,
            n_scenarios_per_duration=n_scen, n_intervals=n_int,
        ):
            try:
                dataset = create_blackout_dataset(
                    frame, scenario, cfg,
                    reference_df=reference_df, source_file=source_file,
                )
            except BlackoutImpossibleError as exc:
                print(f"SKIP {scenario.scenario_id}: {exc}")
                summary["skipped"].append(
                    {"scenario_id": scenario.scenario_id, "reason": exc.reason}
                )
                continue

            report = validate_blackout_frame(
                frame, dataset.frame,
                mask_columns=blackout_cfg.mask_columns,
                availability_column=blackout_cfg.availability_column,
                phase_column=blackout_cfg.phase_column,
                blackout_id_column=blackout_cfg.blackout_id_column,
                allow_overlap=blackout_cfg.allow_overlap,
                min_trip_duration_s=float(blackout_cfg.min_trip_duration_s),
            )
            if not report.ok:
                print(f"FAIL {scenario.scenario_id} (validation):\n{report.summary()}")
                summary["skipped"].append(
                    {"scenario_id": scenario.scenario_id, "reason": "validation_failed"}
                )
                continue

            out_dir = blackout_root / output_cfg.duration_dir(scenario.duration_s)
            out_dir.mkdir(parents=True, exist_ok=True)
            parquet_path = out_dir / output_cfg.trip_file_pattern.format(
                scenario_id=scenario.scenario_id
            )
            meta_path = out_dir / output_cfg.metadata_file_pattern.format(
                scenario_id=scenario.scenario_id
            )
            dataset.frame.to_parquet(parquet_path, index=False)
            meta_path.write_text(
                json.dumps(dataset.metadata(), indent=2), encoding="utf-8"
            )
            summary["ok"] += 1
            made.append(parquet_path)
            print(
                f"OK {scenario.scenario_id}: {scenario.duration_s:g}s, "
                f"{dataset.result.total_masked_samples} rows masked, "
                f"reference={dataset.has_reference}"
            )

    index = build_index(blackout_root, output_cfg)
    index_path = blackout_root / output_cfg.index_file
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    print(
        f"\nDone: {summary['ok']} scenarios written, "
        f"{len(summary['skipped'])} skipped, "
        f"{len(index)} scenarios indexed at {index_path}"
    )
    return 0 if summary["ok"] or blackout_root.exists() else 1


if __name__ == "__main__":
    sys.exit(main())