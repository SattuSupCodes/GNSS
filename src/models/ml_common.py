"""Shared utilities for the navigation-side ML models (D-T3/D-T4/D-T5).

Everything here consumes the *same* 6-channel IMU window the navigation
engine's ``MLInference`` contract exposes::

    IMUWindow  shape (n_windows, WINDOW_SIZE, 6)
    channels   [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z]

Units are m/s^2 (accel) and rad/s (gyro) in the calibrated (device-aligned)
frame, as produced by the Phase 2 calibration pipeline and stored in the
``data/calibrated`` parquet frames.

Trip-level splits come from the canonical ``data/splits/*.txt`` files, so no
trip ever straddles train/validation/test (no intra-trip leakage).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]

WINDOW_SIZE = 100
SENSOR_COLUMNS = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"]
SPLIT_DIR = REPO_ROOT / "data" / "splits"
CALIBRATED_ROOT = REPO_ROOT / "data" / "calibrated"

G_REF = 9.80665


def load_split_trips(split: str) -> list[str]:
    """Load trip ids of one canonical split ('train'/'validation'/'test')."""
    path = SPLIT_DIR / f"{split}_trips.txt"
    if not path.exists():
        raise FileNotFoundError(f"Split file not found: {path}")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_all_split_trips() -> dict[str, list[str]]:
    return {split: load_split_trips(split) for split in ("train", "validation", "test")}


def load_calibrated_trip(trip_id: str, root: Path | None = None) -> pd.DataFrame:
    root = root or CALIBRATED_ROOT
    path = root / f"trip_{trip_id.lower()}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Calibrated trip not found: {path}")
    return pd.read_parquet(path)


def clean_sensor_values(
    frame: pd.DataFrame, extra: list[str] | None = None
) -> pd.DataFrame:
    """Return a per-trip frame with a finite filtered 6-channel sensor block.

    ``extra`` columns (e.g. GNSS truth helpers) are preserved on the returned
    DataFrame, aligned row-for-row with the cleaned sensor block.
    """
    missing = [c for c in SENSOR_COLUMNS if c not in frame.columns]
    if missing:
        return frame.iloc[0:0]
    out = frame.copy()
    out["_v"] = pd.to_numeric(out["speed_kmh"], errors="coerce")
    keep = (
        np.isfinite(out[SENSOR_COLUMNS]).all(axis=1)
        & out[SENSOR_COLUMNS].notna().all(axis=1)
        & out["_v"].notna()
        & out["timestamp"].notna()
    )
    columns = SENSOR_COLUMNS + ["_v", "timestamp", "latitude_deg", "longitude_deg"]
    if extra:
        available = [c for c in extra if c in out.columns]
        columns = columns + available
    return out.loc[keep, columns]


def windowed(frame: pd.DataFrame, window_size: int = WINDOW_SIZE) -> np.ndarray:
    """Shape (n_windows, window_size, 6) (drop-tail windows)."""
    n = len(frame)
    k = n // window_size
    if k == 0:
        return np.zeros((0, window_size, 6), dtype=np.float32)
    sensor = frame[SENSOR_COLUMNS].to_numpy(dtype=np.float64)
    sensor = sensor[: k * window_size]
    return sensor.reshape(k, window_size, 6).astype(np.float32)


def _stats(x: np.ndarray) -> tuple[float, float, float, float]:
    """mean, std, rms, peak-to-peak of an axis over a window."""
    x = np.asarray(x, dtype=np.float64)
    mean = float(np.mean(x))
    std = float(np.std(x))
    rms = float(np.sqrt(np.mean(x * x)))
    ptp = float(np.max(x) - np.min(x))
    return mean, std, rms, ptp


def compute_window_features(windows: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Hand-crafted, physically motivated features from a 6-channel window set.

    Per-window features (``n_windows`` rows):

    * for accel x/y/z and gyro z: mean, std, RMS, peak-to-peak      (16)
    * jerk (sample-to-sample diff) std for each accel axis           (3)
    * mean |accel magnitude - 9.80665|  (vertical energy proxy)      (1)
    * gyro-z diff std  (high-frequency yaw energy)                   (1)

    Total 21 features. All are computable at runtime from the IMU window only
    (no GNSS / reference leakage; no dependency on future data).
    """
    windows = np.asarray(windows, dtype=np.float64)
    if windows.ndim != 3 or windows.shape[2] != 6:
        raise ValueError(f"Expected (n, {WINDOW_SIZE}, 6), got {windows.shape}")

    n = windows.shape[0]
    accel = windows[:, :, :3]
    gyro_z = windows[:, :, 5]

    features = []
    names = []
    for axis, name in zip(range(3), ("x", "y", "z")):
        for stat, label in zip(range(4), ("mean", "std", "rms", "ptp")):
            features.append(np.asarray([_stats(w)[stat] for w in windows[:, :, axis]]))
            names.append(f"accel_{name}_{label}")
    for stat, label in zip(range(4), ("mean", "std", "rms", "ptp")):
        features.append(np.asarray([_stats(w)[stat] for w in gyro_z[:, None]]))
        names.append(f"gyroz_{label}")

    jerk_std = np.std(np.diff(accel, axis=1), axis=1)
    for axis in range(3):
        features.append(jerk_std[:, axis])
        names.append(f"jerk_{['x','y','z'][axis]}_std")

    accel_mag_energy = np.mean(np.abs(np.linalg.norm(accel, axis=2) - G_REF), axis=1)
    features.append(accel_mag_energy)
    names.append("accel_mag_mean_abs_dev")

    gyro_energy = np.std(np.diff(gyro_z, axis=1), axis=1)
    features.append(gyro_energy)
    names.append("gyroz_jerk_std")

    return np.column_stack(features), names


def forward_vec_enu(heading_rad: np.ndarray) -> np.ndarray:
    """Compass heading -> east/north unit vector."""
    heading_rad = np.asarray(heading_rad, dtype=np.float64)
    return np.column_stack([np.sin(heading_rad), np.cos(heading_rad)])


def quat_rotate_array(qw, qx, qy, qz, v):
    """Vectorized quaternion rotate (scalar-first, device->world) of ``v`` (N,3)."""
    q = np.column_stack([qw, qx, qy, qz]).astype(np.float64)
    v = np.asarray(v, dtype=np.float64)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    t = 2.0 * np.cross(q[:, 1:], v)
    return v + q[:, 0, None] * t + np.cross(q[:, 1:], t)


def predict_forest(model, X: np.ndarray) -> np.ndarray:
    """Predict with an sklearn RandomForest WITHOUT the joblib wrapper.

    Equivalent to ``model.predict`` for the two RandomForest flavors used
    here (regression = mean of tree outputs; classification = majority vote),
    but iterates the estimators directly. Recent sklearn versions route every
    single-row predict through ``joblib.delayed`` even at ``n_jobs=1``,
    which costs tens of milliseconds per call at runtime.
    """
    X = np.asarray(X, dtype=np.float64)
    single = X.ndim == 1
    X = X[np.newaxis, :] if single else X

    estimators = list(getattr(model, "estimators_", []) or [])
    if not estimators:
        raise RuntimeError("model has no fitted trees")

    outputs = np.empty((X.shape[0], len(estimators)), dtype=np.float64)
    for col, tree in enumerate(estimators):
        outputs[:, col] = tree.predict(X)

    if hasattr(model, "classes_"):  # classifier: majority vote
        classes = np.asarray(model.classes_)
        preds = []
        for row in outputs.astype(np.int64):
            counts = np.bincount(row, minlength=len(classes))
            preds.append(int(np.argmax(counts)))
        result = classes[np.asarray(preds, dtype=np.int64)]
    else:  # regressor: mean of trees
        result = np.mean(outputs, axis=1)

    if single:
        result = np.atleast_1d(result)[0]
    return result