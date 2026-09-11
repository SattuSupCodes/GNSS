from __future__ import annotations

import argparse
from pathlib import Path

from src.data.dataset_manager import DatasetManager
from src.engine.ds2_evaluation import (
    evaluate_ds2,
    print_ds2_report,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run D-S2 on an Aaqib DatasetManager trip."
    )

    parser.add_argument(
        "trip_id",
        help="Trip ID to load through DatasetManager.",
    )

    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw"),
    )

    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed"),
    )

    parser.add_argument(
        "--calibrated-root",
        type=Path,
        default=Path("data/calibrated"),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )

    args = parser.parse_args()

    manager = DatasetManager(
        raw_root=args.raw_root,
        processed_root=args.processed_root,
        calibrated_root=args.calibrated_root,
    )

    df = manager.load_calibrated_trip(
        args.trip_id
    )

    print(
        f"Loaded trip: {args.trip_id}"
    )

    print(
        f"Rows: {len(df)}"
    )

    print(
        f"Columns: {len(df.columns)}"
    )

    evaluation = evaluate_ds2(df)

    print_ds2_report(evaluation)

    if args.output is not None:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        evaluation.trajectory.to_parquet(
            args.output,
            index=False,
        )

        print()
        print(
            f"Trajectory saved to: {args.output}"
        )


if __name__ == "__main__":
    main()