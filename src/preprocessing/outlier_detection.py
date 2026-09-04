"""Outlier and sensor-glitch handling for IMU + GNSS channels.

Two families of detectors:

* IMU glitches: isolated spikes (single-sample jumps) that physical sensors
  cannot produce. Detected via rolling median absolute deviation.
* GNSS jumps: implausible position jumps between consecutive fixes given the
  elapsed time, e.g. > 60 m/s sustained steps; those fixes are flagged and can
  be dropped or forward-filled.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..data.data_schema import (
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    MAG_X,
    MAG_Y,
    MAG_Z,
    GRAV_X,
    GRAV_Y,
    GRAV_Z,
    GNSS_LAT,
    GNSS_LON,
    TS_SEC,
)

IMU_COLUMNS = [
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    MAG_X,
    MAG_Y,
    MAG_Z,
    GRAV_X,
    GRAV_Y,
    GRAV_Z,
]

_EARTH_R_M = 6371008.8


def _haversine(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1 = np.deg2rad(lat1)
    p2 = np.deg2rad(lat2)
    dp = np.deg2rad(lat2 - lat1)
    dl = np.deg2rad(lon2 - lon1)
    a = (
        np.sin(dp / 2.0) ** 2
        + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    )
    return 2 * _EARTH_R_M * np.arcsin(np.sqrt(a))


def detect_imu_spikes(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    window: int = 15,
    threshold_sigma: float = 8.0,
) -> pd.DataFrame:
    """Return a boolean DataFrame (same shape) marking IMU spikes per column.

    A sample is a spike if it deviates more than ``threshold_sigma`` robust
    standard deviations from the rolling median over ``window`` neighbours.
    """
    cols = [c for c in (columns or IMU_COLUMNS) if c in df.columns]
    flags = pd.DataFrame(index=df.index)
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce")
        median = v.rolling(window, center=True, min_periods=3).median()
        mad = (v - median).abs().rolling(
            window, center=True, min_periods=3
        ).median()
        scale = 1.4826 * mad
        dev = (v - median).abs()
        flags[c] = dev > threshold_sigma * scale
    return flags


def remove_imu_spikes(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    window: int = 15,
    threshold_sigma: float = 8.0,
) -> pd.DataFrame:
    """Replace flagged IMU spikes with NaN (pipeline interpolation restores
    them smoothly), leaving unflagged data untouched."""
    flags = detect_imu_spikes(df, columns, window, threshold_sigma)
    out = df.copy()
    for c in flags.columns:
        out.loc[flags[c], c] = np.nan
    return out


def detect_gnss_jumps(
    df: pd.DataFrame, max_speed_kmh: float = 360.0
) -> pd.Series:
    """Flag GNSS fixes that jump faster than ``max_speed_kmh``.

    Computes haversine speed between consecutive fixes using the timestamp diff.
    Returns a boolean Series (True = jump, to be dropped/ffilled).
    """
    n = len(df)
    flags = pd.Series(False, index=df.index, dtype=bool)
    if n < 2 or GNSS_LAT not in df.columns or GNSS_LON not in df.columns:
        return flags
    lat = pd.to_numeric(df[GNSS_LAT], errors="coerce")
    lon = pd.to_numeric(df[GNSS_LON], errors="coerce")
    ts = pd.to_numeric(df[TS_SEC], errors="coerce") if TS_SEC in df.columns else None

    valid = lat.notna() & lon.notna()
    if ts is not None:
        valid &= ts.notna()

    fix_idx = np.flatnonzero(valid.to_numpy())
    if len(fix_idx) < 2:
        return flags

    i = fix_idx
    d = _haversine(
        lat.to_numpy()[i[:-1]],
        lon.to_numpy()[i[:-1]],
        lat.to_numpy()[i[1:]],
        lon.to_numpy()[i[1:]],
    )
    dt = (
        (ts.to_numpy()[i[1:]] - ts.to_numpy()[i[:-1]])
        if ts is not None
        else np.ones(len(d)) / 10.0
    )
    dt = np.maximum(dt, 1e-6)
    speed_ms = d / dt
    speed_kmh = speed_ms * 3.6

    bad_fix_pairs = speed_kmh > max_speed_kmh
    # flag the second fix of each bad pair (the culprit)
    culprits = i[1:][bad_fix_pairs]
    flags.iloc[culprits] = True
    return flags


def drop_gnss_jumps(df: pd.DataFrame, max_speed_kmh: float = 360.0) -> pd.DataFrame:
    """NaN the lat/lon of flagged jumping fixes so ffill can repair them."""
    flags = detect_gnss_jumps(df, max_speed_kmh=max_speed_kmh)
    out = df.copy()
    for c in (GNSS_LAT, GNSS_LON):
        if c in out.columns:
            out.loc[flags, c] = np.nan
    return out