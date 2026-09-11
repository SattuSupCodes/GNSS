"""D-T4 training: Random Forest longitudinal IMU-correction regressor.

The model maps a ~1 s IMU window to the systematic forward-acceleration error
``corr_x`` (m/s^2). At runtime the adapter rotates the predicted correction to
ENU using the engine's current heading and issues it through
``MLNavigationOutput.accel_correction_enu`` (consumed by the filter's
``update_accel_correction``).

Artifacts:
    models/imu_correction.joblib
    models/imu_correction_metrics.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.models.imu_correction.dataset import build_dataset

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_ROOT / "models" / "imu_correction.joblib"
METRICS_PATH = REPO_ROOT / "models" / "imu_correction_metrics.json"

SEED = 42
N_ESTIMATORS = 300
MAX_DEPTH = 18

TRAIN_SPEED_STD_MPS2 = 1.0  # runtime std attached to the accel correction


def train():
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    print("Building D-T4 datasets...")
    X_train, y_train, names, trips_train = build_dataset("train")
    X_val, y_val, _, trips_val = build_dataset("validation")
    X_test, y_test, _, trips_test = build_dataset("test")
    print(f"  train {X_train.shape}  val {X_val.shape}  test {X_test.shape}")
    print(f"  target stats: mean {np.mean(y_train):.4f} std {np.std(y_train):.4f} m/s^2")

    model = RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        random_state=SEED,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    def evaluate(X, y, trips, split):
        pred = model.predict(X)
        return {
            "split": split,
            "rmse_mps2": float(np.sqrt(mean_squared_error(y, pred))),
            "mae_mps2": float(mean_absolute_error(y, pred)),
            "mean_abs_target_mps2": float(np.mean(np.abs(y))),
            "std_target_mps2": float(np.std(y)),
            "n_samples": int(len(y)),
            "n_trips": int(len(set(trips))),
        }

    val_metrics = evaluate(X_val, y_val, trips_val, "validation")
    test_metrics = evaluate(X_test, y_test, trips_test, "test")

    metrics = {
        "model": "RandomForestRegressor",
        "target": "systematic forward acceleration error (m/s^2), "
                  "GNSS-speed-derived minus measured",
        "feature_names": names,
        "seed": SEED,
        "runtime_std_mps2": TRAIN_SPEED_STD_MPS2,
        "train": evaluate(X_train, y_train, trips_train, "train"),
        "validation": val_metrics,
        "test": test_metrics,
    }

    import joblib

    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nSaved {MODEL_PATH}")
    print(f"Saved {METRICS_PATH}")
    print(f"D-T4 test RMSE: {test_metrics['rmse_mps2']:.4f} m/s^2 "
          f"(MAE {test_metrics['mae_mps2']:.4f})")
    return metrics


if __name__ == "__main__":
    train()