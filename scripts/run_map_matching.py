"""Run GNSS+INS fusion + map matching over a calibrated trip.

Requires a GeoJSON road network. Without one the run degrades to plain
fusion (a warning is printed).

Usage:
    python scripts/run_map_matching.py <trip_id> --map data/maps/road_network.geojson [--config configs/map_matching_config.yaml] [--output ...]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.data.dataset_manager import DatasetManager
from src.engine.engine_trip_runner import (
    load_yaml,
    print_engine_report,
    run_map_matching,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run GNSS+INS fusion with HMM map matching."
    )
    parser.add_argument("trip_id", help="Trip ID to load through DatasetManager.")
    parser.add_argument(
        "--map", type=Path, default=None,
        help="GeoJSON road network (LineString features).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/map_matching_config.yaml"),
    )
    parser.add_argument(
        "--raw-root", type=Path, default=Path("data/raw")
    )
    parser.add_argument(
        "--processed-root", type=Path, default=Path("data/processed")
    )
    parser.add_argument(
        "--calibrated-root", type=Path, default=Path("data/calibrated")
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    config = load_yaml(args.config)
    if "navigation_config" not in config:
        config.update(load_yaml(Path("configs/navigation_config.yaml")))

    manager = DatasetManager(
        raw_root=args.raw_root,
        processed_root=args.processed_root,
        calibrated_root=args.calibrated_root,
    )
    df = manager.load_calibrated_trip(args.trip_id)
    print(f"Loaded trip: {args.trip_id} ({len(df)} rows)")

    map_path = args.map or config.get("map_matching", {}).get("map_geojson")
    if not map_path:
        print(
            "WARNING: no road network provided; map matching disabled, "
            "running plain fusion instead."
        )
        from src.engine.engine_trip_runner import run_fusion

        result = run_fusion(df, config)
    else:
        result = run_map_matching(df, config, Path(map_path))

    print_engine_report(result, title="GNSS + INS FUSION + MAP MATCHING")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.trajectory.to_parquet(args.output, index=False)
        print(f"\nTrajectory saved to: {args.output}")


if __name__ == "__main__":
    main()