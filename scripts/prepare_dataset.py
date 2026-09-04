"""Prepare the Phase 1 canonical dataset from raw IO-VNBD data.

Pipeline:
    1. Discover smartphone trips (S-*.csv) in ``data/raw``.
    2. Extract each trip to a canonical smartphone-only frame.
    3. Run the preprocessing pipeline (cleaning, filtering, resampling,
       normalization, ENU coords, GNSS forward-fill).
    4. Split trips by trip-id (never inside trips) into train/val/test lists.
    5. Write processed trips as Parquet under ``data/processed`` and the split
       lists under ``data/splits``.

Usage:
    python scripts/prepare_dataset.py
    python scripts/prepare_dataset.py --trip vw16b        # single trip
    python scripts/prepare_dataset.py --skip-preprocess   # extract only
    python scripts/prepare_dataset.py --limit 5           # first N trips
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

from src.data.dataset_manager import DatasetManager
from src.data.dataset_splitter import split_trips_by_id
from src.data.io_vnbd_loader import IOVNBDDataset
from src.data.smartphone_extractor import SmartphoneExtractor
from src.preprocessing.preprocessing_pipeline import (
    PipelineConfig,
    PreprocessingPipeline,
)


def load_yaml(name: str) -> dict:
    p = REPO_ROOT / "configs" / name
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trip", type=str, default=None, help="Process only this trip id."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Process only the first N trips."
    )
    parser.add_argument(
        "--skip-preprocess",
        action="store_true",
        help="Only extract + write canonical frames, no preprocessing.",
    )
    parser.add_argument(
        "--splits-only",
        action="store_true",
        help="Only (re)compute the trip-level splits from existing trip ids.",
    )
    parser.add_argument(
        "--config", type=str, default="data_config.yaml", help="Data config."
    )
    args = parser.parse_args()

    cfg = load_yaml(args.config)["dataset"]
    raw_root = REPO_ROOT / cfg["raw_root"]
    processed_root = REPO_ROOT / cfg["processed_root"]
    split_root = REPO_ROOT / cfg["split_root"]

    ds = IOVNBDDataset(str(raw_root))
    manager = DatasetManager(str(raw_root), str(processed_root), str(split_root))
    extractor = SmartphoneExtractor(ds)

    if args.splits_only:
        trips = dm_split_only(manager, split_root)
        print(f"Split written for {len(trips)} trips.")
        return 0

    if args.trip is not None:
        trip_ids = [args.trip]
    else:
        trip_ids = ds.smartphone_trip_ids()
        if args.limit:
            trip_ids = trip_ids[: args.limit]

    if not trip_ids:
        print("No smartphone trips found. Run scripts/download_dataset.py first.")
        return 1

    pipeline = None
    if not args.skip_preprocess:
        pcfg = load_yaml("preprocessing_config.yaml")["pipeline"]
        pipeline = PreprocessingPipeline(PipelineConfig(**pcfg))

    results = []
    for tid in trip_ids:
        path = ds.smartphone_file_for_trip(tid)
        if path is None:
            print(f"SKIP {tid}: no smartphone file")
            continue
        raw = extractor.extract_trip(tid).data
        out = pipeline.run(raw) if pipeline is not None else raw
        out_path = processed_root / f"trip_{tid}.parquet"
        write_parquet(out, out_path)
        results.append(
            {
                "trip_id": tid,
                "rows": int(len(out)),
                "file": str(out_path),
            }
        )
        print(f"OK {tid}: {len(raw)} -> {len(out)} rows -> {out_path.name}")

    if results and not args.skip_preprocess:
        trips = dm_split_only(manager, split_root, verbose=False)
        print(f"\nSplits written for {len(trips)} trips.")

    meta_path = processed_root / cfg.get("metadata_file", "trips_metadata.json")
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {len(results)} trips. Metadata: {meta_path}")
    print("Done.")
    return 0


def split_config() -> dict:
    return load_yaml("data_config.yaml").get("split", {})


def dm_split_only(
    manager: DatasetManager, split_root: Path, verbose: bool = True
) -> list:
    """Compute and persist trip-level train/val/test splits."""
    trip_ids = manager.list_trips()
    split_cfg = split_config()
    ratios = tuple(split_cfg.get("ratios", [0.7, 0.15, 0.15]))
    result = split_trips_by_id(
        trip_ids,
        ratios=ratios,
        shuffle=split_cfg.get("shuffle", True),
        seed=split_cfg.get("seed", 42),
        min_trips_per_split=split_cfg.get("min_trips_per_split", 1),
    )
    if result.warned and verbose:
        print(
            f"WARNING: fewer trips than requested; got "
            f"{result.counts()}"
        )
    split_root.mkdir(parents=True, exist_ok=True)
    for split_name, files_key in (
        ("train", "train"),
        ("validation", "validation"),
        ("test", "test"),
    ):
        ids = getattr(result, files_key)
        out = split_root / split_cfg["output_files"][files_key]
        out.write_text("\n".join(ids) + ("\n" if ids else ""), encoding="utf-8")
    if verbose:
        print(f"Splits: {result.counts()}")
    return trip_ids


if __name__ == "__main__":
    sys.exit(main())