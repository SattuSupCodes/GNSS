"""Run the navigation engine in pure dead-reckoning mode (no GNSS).

Usage:
    python scripts/run_dead_reckoning.py <trip_id> [--config configs/navigation_config.yaml] [--output ...]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.data.dataset_manager import DatasetManager
from src.engine.engine_trip_runner import (
    load_yaml,
    print_engine_report,
    run_dead_reckoning,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run the IDR engine in pure dead-reckoning mode."
    )
    parser.add_argument("trip_id", help="Trip ID to load through DatasetManager.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/navigation_config.yaml"),
        help="Navigation engine YAML config.",
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
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Optional output parquet path for the trajectory.",
    )
    args = parser.parse_args()

    config = load_yaml(args.config)

    manager = DatasetManager(
        raw_root=args.raw_root,
        processed_root=args.processed_root,
        calibrated_root=args.calibrated_root,
    )
    df = manager.load_calibrated_trip(args.trip_id)
    print(f"Loaded trip: {args.trip_id} ({len(df)} rows)")

    result = run_dead_reckoning(df, config)

    print_engine_report(result, title="DEAD RECKONING (NO GNSS)")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.trajectory.to_parquet(args.output, index=False)
        print(f"\nTrajectory saved to: {args.output}")


if __name__ == "__main__":
    main()