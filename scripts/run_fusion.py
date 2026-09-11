"""Run GNSS+INS fusion over a calibrated trip (optionally with blackouts).

Usage:
    python scripts/run_fusion.py <trip_id> [--config configs/navigation_config.yaml] [--scenario data/blackout/60s/xxx.parquet] [--output ...]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.data.dataset_manager import DatasetManager
from src.engine.engine_trip_runner import (
    load_yaml,
    print_engine_report,
    run_fusion,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run EKF/UKF GNSS+INS fusion over a calibrated trip."
    )
    parser.add_argument("trip_id", help="Trip ID to load through DatasetManager.")
    parser.add_argument(
        "--config", type=Path, default=Path("configs/navigation_config.yaml"),
    )
    parser.add_argument(
        "--scenario", type=Path, default=None,
        help="Optional blackout-scenario parquet (data/blackout/<dur>s/<id>.parquet).",
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

    manager = DatasetManager(
        raw_root=args.raw_root,
        processed_root=args.processed_root,
        calibrated_root=args.calibrated_root,
    )

    if args.scenario is not None:
        df = pd.read_parquet(args.scenario)
        print(f"Loaded scenario: {args.scenario} ({len(df)} rows)")
    else:
        df = manager.load_calibrated_trip(args.trip_id)
        print(f"Loaded trip: {args.trip_id} ({len(df)} rows)")

    result = run_fusion(df, config)

    print_engine_report(result, title="GNSS + INS FUSION")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.trajectory.to_parquet(args.output, index=False)
        print(f"\nTrajectory saved to: {args.output}")


if __name__ == "__main__":
    main()