"""D-T5 target generation + dataset for the navigation-error model.

Target (defensible, uses only available reference data):

    drift_rate (m/s) = |DR_pos(t0 + H) - reference_pos(t0 + H)| / H_seconds

* DR position is simulated offline from the *measured* (quaternion-rotated to
  ENU) linear acceleration and GNSS speed, starting at each window.
* reference_pos comes from the trip's own GNSS coordinates (the available
  ground truth for this dataset; no vehicle reference files exist locally).
* Window IMU features + last-known speed are the only *inputs* at runtime:
  expected position error is ``drift_rate * gnss_age`` (the engine knows how
  long the GNSS has been out).

No future reference information is used in any input feature.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import ml_common as mc

HORIZON_SAMPLES = 150          # ~1.5 s of simulated dead reckoning per window
WINDOW_STRIDE = 150            # one model sample every ~1.5 s of trip
EARTH_RADIUS_M = 6_378_137.0
MAX_DRIFT_RATE_MPS = 25.0      # clip implausible outlier targets


def _trip_reference_enu(frame: pd.DataFrame) -> np.ndarray:
    lat = np.radians(pd.to_numeric(frame["latitude_deg"], errors="coerce").to_numpy(dtype=np.float64))
    lon = np.radians(pd.to_numeric(frame["longitude_deg"], errors="coerce").to_numpy(dtype=np.float64))
    lat0, lon0 = lat[0], lon[0]
    east = (lon - lon0) * np.cos(lat0) * EARTH_RADIUS_M
    north = (lat - lat0) * EARTH_RADIUS_M
    return np.column_stack([east, north])


def _trip_measured_accel_enu(frame: pd.DataFrame) -> np.ndarray:
    linear = np.column_stack(
        [
            pd.to_numeric(frame[c], errors="coerce").to_numpy(dtype=np.float64)
            for c in ("linear_accel_x", "linear_accel_y", "linear_accel_z")
        ]
    )
    ac = mc.quat_rotate_array(
        pd.to_numeric(frame["orient_qw"], errors="coerce").to_numpy(dtype=np.float64),
        pd.to_numeric(frame["orient_qx"], errors="coerce").to_numpy(dtype=np.float64),
        pd.to_numeric(frame["orient_qy"], errors="coerce").to_numpy(dtype=np.float64),
        pd.to_numeric(frame["orient_qz"], errors="coerce").to_numpy(dtype=np.float64),
        linear,
    )
    return ac[:, :2]


def _simulate_drift(err, v0, h0, accel_e, accel_n, gyro_z, dt):
    """Integrate DR one window; return (drift_enu_vec, elapsed_s)."""
    v_e = np.cumsum(accel_e * dt) + v0[0]
    v_n = np.cumsum(accel_n * dt) + v0[1]
    pos_e = np.cumsum(v_e * dt)
    pos_n = np.cumsum(v_n * dt)
    return np.asarray([pos_e[-1], pos_n[-1]], dtype=np.float64), float(np.sum(dt))


def build_dataset(split: str, window_size: int = mc.WINDOW_SIZE, horizon: int = HORIZON_SAMPLES):
    trip_ids = mc.load_split_trips(split)
    X_list, y_list, meta_list = [], [], []
    names = None
    for trip_id in trip_ids:
        try:
            raw = mc.load_calibrated_trip(trip_id)
        except FileNotFoundError:
            continue
        if not {"linear_accel_x", "orient_qw", "speed_kmh"} <= set(raw.columns):
            continue
        frame = mc.clean_sensor_values(
            raw,
            extra=[
                "linear_accel_x", "linear_accel_y", "linear_accel_z",
                "orient_qw", "orient_qx", "orient_qy", "orient_qz",
                "gps_heading_deg",
            ],
        )
        n = len(frame)
        if n < window_size + horizon:
            continue

        accel_enu = _trip_measured_accel_enu(frame)
        ref_enu = _trip_reference_enu(frame)
        gyro_z = frame["gyro_z"].astype(np.float64).to_numpy()
        timestamp = frame["timestamp"].astype(np.float64).to_numpy()
        dt = np.diff(timestamp)
        speed = frame["_v"].to_numpy(dtype=np.float64) / 3.6
        heading0 = np.radians(
            pd.to_numeric(frame["gps_heading_deg"], errors="coerce").to_numpy(dtype=np.float64)
        )
        forward = mc.forward_vec_enu(heading0)

        starts = range(0, n - window_size - horizon, WINDOW_STRIDE)
        for i in starts:
            seg = slice(i, i + window_size)
            windows = frame.iloc[i : i + window_size]
            w = mc.windowed(windows)  # shape (1, W, 6) when >= window_size
            if w.shape[0] != 1:
                continue
            feat, names = mc.compute_window_features(w)

            j = i + window_size  # drift simulation starts right after window
            h = seg_len = min(horizon, n - j)
            if h < 2:
                continue
            dt_slice = dt[j : j + h - 1]
            if np.any(dt_slice <= 0.0) or not np.all(np.isfinite(dt_slice)):
                continue

            v0 = speed[i] * forward[i]
            drift_enu, elapsed = _simulate_drift(
                None,
                v0,
                heading0[i],
                accel_enu[j : j + h - 1, 0],
                accel_enu[j : j + h - 1, 1],
                gyro_z[j : j + h - 1],
                dt_slice,
            )
            if elapsed <= 1e-6:
                continue
            ref_drift = ref_enu[i + window_size + h - 1] - ref_enu[i]
            target = min(
                np.linalg.norm(drift_enu - ref_drift) / elapsed, MAX_DRIFT_RATE_MPS
            )

            row = np.concatenate([feat[0], [speed[i]]])
            if not np.all(np.isfinite(row)) or not np.isfinite(target):
                continue
            X_list.append(row)
            y_list.append(target)
            meta_list.append(trip_id)

    if not X_list:
        raise RuntimeError(f"No D-T5 window data produced for split '{split}'")
    X = np.vstack(X_list).astype(np.float32)
    y = np.asarray(y_list, dtype=np.float32)
    trips = np.asarray(meta_list, dtype=object)
    if names is not None:
        names = names + ["speed_mps"]
    return X, y, names, trips