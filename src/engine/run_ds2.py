from __future__ import annotations

import argparse
from pathlib import Path

from src.engine.ds2_evaluation import (
    evaluate_ds2,
    print_ds2_report,
)


def main():
    parser = argparse.ArgumentParser(
        description="Run D-S2 inertial navigation on a calibrated trip."
    )

    parser.add_argument(
        "trip_file",
        type=Path,
        help="Path to calibrated trip parquet file.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output trajectory parquet path.",
    )

    args = parser.parse_args()

    if not args.trip_file.exists():
        raise FileNotFoundError(
            f"Trip file not found: {args.trip_file}"
        )

    df = __import__("pandas").read_parquet(
        args.trip_file
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