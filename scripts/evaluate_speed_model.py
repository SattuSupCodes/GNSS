"""Evaluate the trained LSTM speed estimator on the held-out test set."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.models.speed_estimator.inference import SpeedEstimator


TEST_PATH = Path("data/testing/sequences.parquet")

FEATURE_COLUMNS = [
    "accel_x_cal",
    "accel_y_cal",
    "accel_z_cal",
    "gyro_x_cal",
    "gyro_y_cal",
    "gyro_z_cal",
    "mag_x_cal",
    "mag_y_cal",
    "mag_z_cal",
]

TARGET_COLUMN = "speed_kmh"

# A sequence is considered stationary when its reference
# speed never exceeds this threshold.
STATIONARY_THRESHOLD_KMH = 1.0

# Save detailed sequence-level results here.
OUTPUT_PATH = Path("models/speed_test_sequence_results.csv")


def calculate_metrics(actual, predicted):
    """Calculate MAE and RMSE."""

    actual = np.asarray(actual, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)

    valid = (
        np.isfinite(actual)
        & np.isfinite(predicted)
    )

    actual = actual[valid]
    predicted = predicted[valid]

    if len(actual) == 0:
        return {
            "samples": 0,
            "mae_kmh": np.nan,
            "rmse_kmh": np.nan,
        }

    error = predicted - actual

    mae = np.mean(np.abs(error))
    rmse = np.sqrt(np.mean(error ** 2))

    return {
        "samples": len(actual),
        "mae_kmh": mae,
        "rmse_kmh": rmse,
    }


def main():

    print("=" * 70)
    print("LSTM SPEED MODEL — DETAILED TEST EVALUATION")
    print("=" * 70)

    # --------------------------------------------------------
    # Load test data
    # --------------------------------------------------------

    print()
    print(f"Loading test data: {TEST_PATH}")

    df = pd.read_parquet(TEST_PATH)

    required_columns = (
        ["sequence_id", "trip_id", TARGET_COLUMN]
        + FEATURE_COLUMNS
    )

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    print(
        f"Rows: {len(df):,}"
    )

    print(
        f"Sequences: {df['sequence_id'].nunique():,}"
    )

    # --------------------------------------------------------
    # Load trained model
    # --------------------------------------------------------

    print()
    print("Loading trained LSTM...")

    estimator = SpeedEstimator()

    print(
        f"Device: {estimator.device}"
    )

    # --------------------------------------------------------
    # Evaluate every sequence
    # --------------------------------------------------------

    results = []

    all_actual = []
    all_predicted = []

    stationary_actual = []
    stationary_predicted = []

    moving_actual = []
    moving_predicted = []

    sequence_count = 0

    print()
    print("Evaluating sequences...")

    for sequence_id, group in df.groupby(
        "sequence_id",
        sort=False,
    ):

        group = group.sort_values(
            "sample_in_window"
        )

        # We require exactly 100 samples.
        if len(group) != 100:
            continue

        x = group[
            FEATURE_COLUMNS
        ].to_numpy(
            dtype=np.float32
        )

        actual = group[
            TARGET_COLUMN
        ].to_numpy(
            dtype=np.float32
        )

        # Skip sequences with invalid reference targets.
        if not np.isfinite(actual).all():
            continue

        predicted = estimator.predict(x)

        # ----------------------------------------------------
        # Sequence classification
        # ----------------------------------------------------

        reference_max_speed = np.max(actual)

        if reference_max_speed <= STATIONARY_THRESHOLD_KMH:
            category = "stationary"

            stationary_actual.extend(actual)
            stationary_predicted.extend(predicted)

        else:
            category = "moving"

            moving_actual.extend(actual)
            moving_predicted.extend(predicted)

        all_actual.extend(actual)
        all_predicted.extend(predicted)

        # ----------------------------------------------------
        # Sequence metrics
        # ----------------------------------------------------

        metrics = calculate_metrics(
            actual,
            predicted,
        )

        results.append({
            "sequence_id": sequence_id,
            "trip_id": group["trip_id"].iloc[0],
            "category": category,
            "reference_mean_speed_kmh": float(
                np.mean(actual)
            ),
            "reference_max_speed_kmh": float(
                np.max(actual)
            ),
            "predicted_mean_speed_kmh": float(
                np.mean(predicted)
            ),
            "predicted_max_speed_kmh": float(
                np.max(predicted)
            ),
            "mae_kmh": metrics["mae_kmh"],
            "rmse_kmh": metrics["rmse_kmh"],
        })

        sequence_count += 1

        if sequence_count % 500 == 0:
            print(
                f"  Evaluated {sequence_count:,} sequences..."
            )

    # --------------------------------------------------------
    # Overall metrics
    # --------------------------------------------------------

    overall = calculate_metrics(
        all_actual,
        all_predicted,
    )

    stationary = calculate_metrics(
        stationary_actual,
        stationary_predicted,
    )

    moving = calculate_metrics(
        moving_actual,
        moving_predicted,
    )

    # --------------------------------------------------------
    # Sequence-level statistics
    # --------------------------------------------------------

    results_df = pd.DataFrame(results)

    stationary_sequences = int(
        (results_df["category"] == "stationary").sum()
    )

    moving_sequences = int(
        (results_df["category"] == "moving").sum()
    )

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)

    print()
    print("OVERALL TEST SET")
    print(
        f"  Sequences: {sequence_count:,}"
    )
    print(
        f"  Samples:   {overall['samples']:,}"
    )
    print(
        f"  MAE:       {overall['mae_kmh']:.4f} km/h"
    )
    print(
        f"  RMSE:      {overall['rmse_kmh']:.4f} km/h"
    )

    print()
    print("STATIONARY SEQUENCES")
    print(
        f"  Sequences: {stationary_sequences:,}"
    )
    print(
        f"  Samples:   {stationary['samples']:,}"
    )
    print(
        f"  MAE:       {stationary['mae_kmh']:.4f} km/h"
    )
    print(
        f"  RMSE:      {stationary['rmse_kmh']:.4f} km/h"
    )

    print()
    print("MOVING SEQUENCES")
    print(
        f"  Sequences: {moving_sequences:,}"
    )
    print(
        f"  Samples:   {moving['samples']:,}"
    )
    print(
        f"  MAE:       {moving['mae_kmh']:.4f} km/h"
    )
    print(
        f"  RMSE:      {moving['rmse_kmh']:.4f} km/h"
    )

    # --------------------------------------------------------
    # Worst sequences
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("10 WORST SEQUENCES BY MAE")
    print("=" * 70)

    worst = results_df.sort_values(
        "mae_kmh",
        ascending=False,
    ).head(10)

    print(
        worst[
            [
                "sequence_id",
                "trip_id",
                "category",
                "reference_mean_speed_kmh",
                "predicted_mean_speed_kmh",
                "mae_kmh",
                "rmse_kmh",
            ]
        ].to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Save detailed results
    # --------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print(
        f"Detailed results saved → {OUTPUT_PATH}"
    )

    print()
    print("=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()