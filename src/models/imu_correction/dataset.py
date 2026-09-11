"""D-T4 target generation + window dataset for the IMU-correction model.

Target (defensible, uses only available reference data):

    The systematic longitudinal acceleration error over a ~1 s window:

        corr_x = mean(ref_forward_accel) - mean(measured_forward_accel)

    * ``ref_forward_accel``      = (speed_end - speed_start) / window_duration,
        speed from GNSS ``speed_kmh`` (reference truth during healthy GNSS).
    * ``measured_forward_accel`` = projection of the quaternion-rotated
        linear acceleration (ENU) onto the compass-forward direction.

``window`` = 6-channel calibrated IMU window (the model input at runtime).
``speed_kmh`` is used ONLY to build the training target; it is not a feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import ml_common as mc

MIN_SPEED_KMH = 1.0   # ignore near-stationary windows (no stable GNSS truth)
MAX_CORR_MPS2 = 5.0   # clip implausible target values
GYRO_BIAS_STD_RADPS = 0.005


def _measured_forward_accel(frame: pd.DataFrame) -> np.ndarray:
    """Per-sample forward acceleration (m/s^2) from data, vectorized."""
    linear = np.column_stack(
        [
            pd.to_numeric(frame[c], errors="coerce").to_numpy(dtype=np.float64)
            for c in ("linear_accel_x", "linear_accel_y", "linear_accel_z")
        ]
    )
    q = frame[["orient_qw", "orient_qx", "orient_qy", "orient_qz"]]
    accel_enu = mc.quat_rotate_array(
        pd.to_numeric(q["orient_qw"], errors="coerce").to_numpy(dtype=np.float64),
        pd.to_numeric(q["orient_qx"], errors="coerce").to_numpy(dtype=np.float64),
        pd.to_numeric(q["orient_qy"], errors="coerce").to_numpy(dtype=np.float64),
        pd.to_numeric(q["orient_qz"], errors="coerce").to_numpy(dtype=np.float64),
        linear,
    )
    heading = np.radians(
        pd.to_numeric(frame["gps_heading_deg"], errors="coerce").to_numpy(dtype=np.float64)
    )
    forward = mc.forward_vec_enu(heading)
    meas = np.sum(accel_enu[:, :2] * forward, axis=1)
    return np.nan_to_num(meas, nan=0.0, posinf=0.0, neginf=0.0)


def build_dataset(split: str, window_size: int = mc.WINDOW_SIZE):
    """Return (X, y_corr, names, trips) for one split."""
    trip_ids = mc.load_split_trips(split)
    X_list, y_list, meta_list = [], [], []
    names = None
    for trip_id in trip_ids:
        try:
            raw = mc.load_calibrated_trip(trip_id)
        except FileNotFoundError:
            continue
        if "linear_accel_x" not in raw.columns or "speed_kmh" not in raw.columns:
            continue
        # Keep only stationary-valid sensor windows on the 6-channel block,
        # but compute the forward-accel reference using all samples.
        frame = mc.clean_sensor_values(
            raw,
            extra=[
                "linear_accel_x", "linear_accel_y", "linear_accel_z",
                "orient_qw", "orient_qx", "orient_qy", "orient_qz",
                "gps_heading_deg",
            ],
        )
        if len(frame) < window_size + 1:
            continue

        meas_fwd = _measured_forward_accel(frame)

        n_windows = len(frame) // window_size
        if n_windows == 0:
            continue
        block = frame.iloc[: n_windows * window_size]
        windows = mc.windowed(frame, window_size)
        if windows.shape[0] == 0:
            continue
        feat, names = mc.compute_window_features(windows)

        speed = block["_v"].astype(np.float64).to_numpy()
        speed_w = speed.reshape(n_windows, window_size)
        speed_start = speed_w[:, 0]
        speed_end = speed_w[:, -1]
        dt_window = block["timestamp"].astype(np.float64).to_numpy()
        dt_w = dt_window.reshape(n_windows, window_size)
        duration = dt_w[:, -1] - dt_w[:, 0]
        duration = np.maximum(duration, 1e-3)

        ref_accel = (speed_end - speed_start) / 3.6 / duration
        meas_fwd_w = meas_fwd[: n_windows * window_size].reshape(n_windows, window_size)
        meas_accel = np.mean(meas_fwd_w, axis=1)

        target = np.clip(ref_accel - meas_accel, -MAX_CORR_MPS2, MAX_CORR_MPS2)

        valid = (
            np.isfinite(feat).all(axis=1)
            & (np.mean(speed_w, axis=1) > MIN_SPEED_KMH)
            & np.isfinite(target)
        )
        if not valid.any():
            continue
        X_list.append(feat[valid])
        y_list.append(target[valid])
        meta_list.append(np.full(int(valid.sum()), trip_id, dtype=object))

    if not X_list:
        raise RuntimeError(f"No D-T4 window data produced for split '{split}'")
    X = np.vstack(X_list).astype(np.float32)
    y = np.concatenate(y_list).astype(np.float32)
    trips = np.concatenate(meta_list)
    return X, y, names, trips