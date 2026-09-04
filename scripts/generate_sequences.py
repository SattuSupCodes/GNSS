"""Generate ML-ready fixed-length window sequences from calibrated/processed trips.

Respects the Phase 1 trip-level split files (data/splits/*.txt): each trip is
assigned to exactly one split, and windows are generated within each trip, so no
window crosses a trip boundary and no trip id appears in more than one split.

Reads calibrated trips first (data/calibrated); any trip without a calibrated
file falls back to its processed frame.

Usage:
    python scripts/generate_sequences.py
    python scripts/generate_sequences.py --window-rows 200 --stride-rows 100
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

from src.data.dataset_manager import DatasetManager
from src.data.io_vnbd_loader import IOVNBDDataset
from src.data.sequence_generator import (
    WindowConfig,
    generate_windows_for_trips,
    load_split_assignments,
    write_sequences,
)

SPLITS = ("train", "validation", "test")


def load_yaml(name: str) -> dict:
    p = REPO_ROOT / "configs" / name
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-rows", type=int, default=None)
    parser.add_argument("--stride-rows", type=int, default=None)
    parser.add_argument("--config", type=str, default="calibration_config.yaml")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N split-assigned trips (dev convenience).",
    )
    args = parser.parse_args()

    data_cfg = load_yaml("data_config.yaml")["dataset"]
    raw_root = REPO_ROOT / data_cfg["raw_root"]
    processed_root = REPO_ROOT / data_cfg["processed_root"]
    manager = DatasetManager(str(raw_root), str(processed_root))
    IOVNBDDataset(str(raw_root)).check_smartphone_data_available()

    seq_cfg = load_yaml(args.config).get("sequence", {})
    window_rows = args.window_rows or int(seq_cfg.get("window_rows", 100))
    stride_rows = args.stride_rows or int(seq_cfg.get("stride_rows", 100))
    drop_tail = bool(seq_cfg.get("drop_incomplete_tail", True))
    wcfg = WindowConfig(
        window_rows=window_rows,
        stride_rows=stride_rows,
        drop_incomplete_tail=drop_tail,
        columns=seq_cfg.get("sensor_columns") or None,
    )

    assignment = load_split_assignments(manager.split_root)
    if not assignment:
        print("No split assignment found. Run scripts/prepare_dataset.py first.")
        return 1

    trips = {}
    for tid in sorted(set(assignment)):
        if args.limit and len(trips) >= args.limit:
            break
        try:
            if tid in manager.calibrated_trips():
                df = manager.load_calibrated_trip(tid)
            else:
                df = manager.load_processed_trip(tid).data
        except FileNotFoundError as exc:
            print(f"SKIP {tid}: {exc}")
            continue
        if df is None or len(df) < wcfg.window_rows:
            print(f"SKIP {tid}: only {0 if df is None else len(df)} rows (< window)")
            continue
        trips[tid] = df

    windows = generate_windows_for_trips(trips, wcfg, split_assignment=assignment, splits=SPLITS)

    out_cfg = seq_cfg.get("output", {})
    out_root = REPO_ROOT / out_cfg.get("root", "data").lstrip("./").strip()
    counts = write_sequences(windows, out_root, splits=SPLITS)

    meta_file = out_root / out_cfg.get("metadata_file", "sequences_metadata.json")
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    meta_file.write_text(
        json.dumps(
            {
                "window_rows": wcfg.window_rows,
                "stride_rows": wcfg.stride_rows,
                "drop_incomplete_tail": wcfg.drop_incomplete_tail,
                "columns": wcfg.columns,
                "n_trips": len(trips),
                "n_windows_per_split": counts,
                "split_file_pattern": "data/training/sequences.parquet (etc.)",
                "provenance_columns": [
                    "sequence_id", "trip_id", "split", "window_index",
                    "window_start_timestamp", "window_stop_timestamp",
                    "sample_in_window",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Window config: {window_rows} samples, stride {stride_rows}")
    print("Windows per split:", counts)
    print(f"Metadata: {meta_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())