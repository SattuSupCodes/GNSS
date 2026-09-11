"""D-T5 training: Random Forest navigation-error (drift-rate) model."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.models.fusion_correction.dataset import build_dataset

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_ROOT / "models" / "error_model.joblib"
METRICS_PATH = REPO_ROOT / "models" / "error_model_metrics.json"

SEED = 42
N_ESTIMATORS = 300
MAX_DEPTH = 18


def train():
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error

    print("Building D-T5 datasets (offline DR simulation)...")
    X_train, y_train, names, trips_train = build_dataset("train")
    X_val, y_val, _, trips_val = build_dataset("validation")
    X_test, y_test, _, trips_test = build_dataset("test")
    print(f"  train {X_train.shape}  val {X_val.shape}  test {X_test.shape}")
    print(f"  drift-rate stats: mean {np.mean(y_train):.4f} m/s "
          f"(std {np.std(y_train):.4f})")

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
            "rmse_mps": float(np.sqrt(mean_squared_error(y, pred))),
            "mae_mps": float(mean_absolute_error(y, pred)),
            "mean_abs_target_mps": float(np.mean(np.abs(y))),
            "n_samples": int(len(y)),
            "n_trips": int(len(set(trips))),
        }

    val_metrics = evaluate(X_val, y_val, trips_val, "validation")
    test_metrics = evaluate(X_test, y_test, trips_test, "test")

    metrics = {
        "model": "RandomForestRegressor",
        "target": "dead-reckoning drift rate (m/s) over ~6 s simulation "
                  "against GNSS reference",
        "feature_names": names,
        "seed": SEED,
        "runtime_use": "expected_position_error_m = drift_rate * gnss_age",
        "train": evaluate(X_train, y_train, trips_train, "train"),
        "validation": val_metrics,
        "test": test_metrics,
    }

    import joblib

    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nSaved {MODEL_PATH}")
    print(f"Saved {METRICS_PATH}")
    print(f"D-T5 test RMSE: {test_metrics['rmse_mps']:.4f} m/s "
          f"(MAE {test_metrics['mae_mps']:.4f})")
    return metrics


if __name__ == "__main__":
    train()