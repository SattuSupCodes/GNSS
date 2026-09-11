"""D-T3 label generation + window dataset for the vibration classifier.

Labels are derived from the real calibrated data with a transparent,
deterministic physical rule (documented in docs/ml_models.md):

* ``stationary`` : mean window speed < ``STATIONARY_SPEED_KMH``.
* ``vibration``  : moving window whose IMU high-frequency energy exceeds the
  ``VIBRATION_*`` thresholds (vertical accel energy, jerk magnitude, or yaw
  jerk). Physically these fire on potholes / speed bumps / rough roads.
* ``normal``     : everything else (moving, smooth).

IMU-window features only (``ml_common.compute_window_features``); speed is used
exclusively to *label* and never becomes a model input.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.models import ml_common as mc

CLASSES = ["stationary", "normal", "vibration"]

# --- deterministic label thresholds (physical units) ----------------------- #
STATIONARY_SPEED_KMH = 0.5
VIBRATION_MAG_ABS_DEV_MPS2 = 0.35   # mean |mag(accel) - g| over ~1 s
VIBRATION_JERK_STD_MPS2 = 0.8       # std of sample-to-sample accel diff
VIBRATION_GYRO_JERK_RADPS = 0.25    # std of yaw-rate diffs


def label_window(speed_mean_kmh: float, features: dict) -> str:
    """Label a single window (deterministic, explainable)."""
    if speed_mean_kmh < STATIONARY_SPEED_KMH:
        return "stationary"
    if (
        features.get("accel_mag_mean_abs_dev", 0.0) > VIBRATION_MAG_ABS_DEV_MPS2
        or features.get("jerk_z_std", 0.0) > VIBRATION_JERK_STD_MPS2
        or features.get("gyroz_jerk_std", 0.0) > VIBRATION_GYRO_JERK_RADPS
    ):
        return "vibration"
    return "normal"


def build_dataset(split: str, window_size: int = mc.WINDOW_SIZE):
    """Return (X, y, names, windows) for one split across all its trips."""
    trip_ids = mc.load_split_trips(split)
    X_list, y_list, meta_list = [], [], []
    names = None
    for trip_id in trip_ids:
        try:
            frame = mc.clean_sensor_values(mc.load_calibrated_trip(trip_id))
        except FileNotFoundError:
            continue
        if len(frame) < window_size:
            continue
        windows = mc.windowed(frame, window_size)
        if windows.shape[0] == 0:
            continue
        feat, names = mc.compute_window_features(windows)

        speed_kmh = frame["_v"].to_numpy(dtype=np.float64)
        speed_windows = speed_kmh[: windows.shape[0] * window_size].reshape(
            windows.shape[0], window_size
        )

        labels = []
        for i in range(windows.shape[0]):
            fd = {names[j]: feat[i, j] for j in range(len(names))}
            labels.append(label_window(float(np.mean(speed_windows[i])), fd))
        y = np.asarray(labels, dtype=object)

        valid = np.isfinite(feat).all(axis=1) & (pd.Series(labels).notna().to_numpy())
        if not valid.any():
            continue
        X_list.append(feat[valid])
        y_list.append(y[valid])
        meta_list.append(
            np.full(int(valid.sum()), trip_id, dtype=object)
        )

    if not X_list:
        raise RuntimeError(f"No window data produced for split '{split}'")
    X = np.vstack(X_list).astype(np.float32)
    y = np.concatenate(y_list)
    trips = np.concatenate(meta_list)
    return X, y, names, trips


def class_counts(y: np.ndarray) -> dict[str, int]:
    return {c: int(np.sum(y == c)) for c in CLASSES}