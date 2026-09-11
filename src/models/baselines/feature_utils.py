"""Shared feature engineering for the classical (D-T1) baselines.

The neural models see a whole 100-sample sensor window. Classical regressors
do not understand sequence structure, so each timestep is represented by
strictly-causal statistics (value so far + expanding mean + expanding std).
Nothing at time ``t`` uses samples after ``t``, so no future information leaks.
"""

import numpy as np

from src.models.speed_estimator.dataset import SpeedSequenceDataset


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

#: Causal feature layout: instantaneous (9) + expanding mean (9) + exp std (9).
FEATURE_DIM = 3 * len(FEATURE_COLUMNS)


def load_sequences(parquet_path: str):
    """Return (x, y, mask) arrays for a sequence-split parquet file."""
    dataset = SpeedSequenceDataset(parquet_path)

    x = np.stack([item[0].numpy() for item in dataset])
    y = np.stack([item[1].numpy() for item in dataset])
    mask = np.stack([item[2].numpy() for item in dataset])

    return x, y, mask


def build_causal_features(x: np.ndarray) -> np.ndarray:
    """Convert an (B, T, C) window batch into (B, T, 3*C) causal features.

    For timestep ``t`` the features are:
        [x[t], expanding_mean(x[:t+1]), expanding_std(x[:t+1])]
    """
    x = np.asarray(x, dtype=np.float32)

    counts = np.arange(1, x.shape[1] + 1, dtype=np.float32)[:, None]

    cumulative_sum = np.cumsum(x, axis=1)
    cumulative_mean = cumulative_sum / counts

    cumulative_sq = np.cumsum(x * x, axis=1)
    cumulative_var = cumulative_sq / counts - cumulative_mean ** 2
    cumulative_var = np.clip(cumulative_var, 0.0, None)
    cumulative_std = np.sqrt(cumulative_var)

    return np.concatenate(
        [x, cumulative_mean, cumulative_std],
        axis=2,
    )


def calculate_metrics(actual, predicted, mask):
    """Masked RMSE/MAE on the same per-sample definition as the neural models."""
    actual = np.asarray(actual, dtype=np.float64)
    predicted = np.asarray(predicted, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)

    actual = actual[mask]
    predicted = predicted[mask]

    if actual.size == 0:
        return {
            "samples": 0,
            "mse": float("nan"),
            "rmse": float("nan"),
            "mae": float("nan"),
        }

    error = predicted - actual

    mse = float(np.mean(error ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(error)))

    return {
        "samples": int(actual.size),
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
    }