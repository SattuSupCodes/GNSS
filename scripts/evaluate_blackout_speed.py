import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.speed_estimator.inference import SpeedEstimator


BLACKOUT_ROOT = Path("data/blackout")
OUTPUT = Path("models/blackout_speed_predictions.csv")

FEATURES = [
    "accel_x_cal", "accel_y_cal", "accel_z_cal",
    "gyro_x_cal", "gyro_y_cal", "gyro_z_cal",
    "mag_x_cal", "mag_y_cal", "mag_z_cal",
]

WINDOW_SIZE = 100


def main():
    estimator = SpeedEstimator(
        model_path="models/speed_lstm.pt",
        scaler_path="models/speed_lstm_scaler.npz",
    )

    rows = []
    files = sorted(BLACKOUT_ROOT.glob("*/*.parquet"))

    print(f"Blackout files found: {len(files)}")

    for i, path in enumerate(files, 1):
        df = pd.read_parquet(path)

        if "blackout_phase" not in df.columns:
            continue

        # Only use runtime sensor data.
        missing = [c for c in FEATURES if c not in df.columns]
        if missing:
            print(f"SKIP {path}: missing {missing}")
            continue

        # Find contiguous 100-sample windows.
        n = len(df)

        for start in range(0, n - WINDOW_SIZE + 1, WINDOW_SIZE):
            end = start + WINDOW_SIZE
            window = df.iloc[start:end].copy()

            # We only need predictions for windows containing blackout samples.
            blackout_mask = (
                window["blackout_phase"].eq("blackout")
                | (~window["gnss_available"].astype(bool))
            )

            if not blackout_mask.any():
                continue

            x = (
                window[FEATURES]
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
                .to_numpy(dtype=np.float32)
            )

            try:
                pred = estimator.predict(x)
            except Exception as exc:
                print(f"SKIP {path} window {start}: {exc}")
                continue

            for j in np.where(blackout_mask.to_numpy())[0]:
                row = window.iloc[j]

                rows.append({
                    "scenario_id": path.stem,
                    "trip_id": str(row["trip_id"]),
                    "timestamp": float(row["timestamp"]),
                    "blackout_phase": str(row["blackout_phase"]),
                    "gnss_available": bool(row["gnss_available"]),
                    "reference_speed_kmh": np.nan,
                    "predicted_speed_kmh": float(pred[j]),
                })

        if i % 50 == 0:
            print(f"Processed {i}/{len(files)} blackout files...")

    out = pd.DataFrame(rows)

    if out.empty:
        raise RuntimeError("No blackout predictions were generated.")

    # Offline-only ground truth:
    # recover the original speed from the clean calibrated trip.
    # This is NOT supplied to the ML model.
    for trip_id in out["trip_id"].unique():
        ref_path = Path("data/calibrated") / f"trip_{trip_id.lower()}.parquet"

        if not ref_path.exists():
            print(f"WARNING: reference file missing for {trip_id}")
            continue

        ref = pd.read_parquet(ref_path, columns=["timestamp", "speed_kmh"])

        ref["timestamp"] = pd.to_numeric(ref["timestamp"], errors="coerce")
        ref["speed_kmh"] = pd.to_numeric(ref["speed_kmh"], errors="coerce")

        mask = out["trip_id"].eq(trip_id)

        merged = out.loc[mask, ["timestamp"]].merge(
            ref,
            on="timestamp",
            how="left",
        )

        out.loc[mask, "reference_speed_kmh"] = (
            merged["speed_kmh"].to_numpy()
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT, index=False)

    valid = out["reference_speed_kmh"].notna()
    err = (
        out.loc[valid, "predicted_speed_kmh"]
        - out.loc[valid, "reference_speed_kmh"]
    )

    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))

    print()
    print("=" * 70)
    print("BLACKOUT SPEED EVALUATION")
    print("=" * 70)
    print(f"Blackout samples: {len(out):,}")
    print(f"Scenarios:        {out['scenario_id'].nunique():,}")
    print(f"MAE:              {mae:.4f} km/h")
    print(f"RMSE:             {rmse:.4f} km/h")
    print()
    print(f"Predictions saved -> {OUTPUT}")


if __name__ == "__main__":
    main()
