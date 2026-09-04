"""Data cleaning utilities for canonical trip frames.

All functions operate on a canonical smartphone-only frame (see
``src.data.data_schema``). They are pure and DataFrame-in/DataFrame-out so they
compose inside the preprocessing pipeline.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from ..data.data_schema import (
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    DATETIME,
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

# Sensor columns that must never contain NaN after cleaning (IMU + gravity).
_IMU_COLS = [
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

# GNSS columns are sparse by design (only ~1-10% of rows have a fix); they are
# cleaned differently and never forced to be non-null.
_GNSS_COLS = [GNSS_LAT, GNSS_LON]


def drop_na_rows(
    df: pd.DataFrame, subset: Optional[List[str]] = None
) -> pd.DataFrame:
    """Drop rows with missing values in ``subset`` (default: IMU columns)."""
    cols = subset if subset is not None else _IMU_COLS
    cols = [c for c in cols if c in df.columns]
    out = df.dropna(subset=cols)
    return out


def drop_duplicate_timestamps(
    df: pd.DataFrame, keep: str = "first"
) -> pd.DataFrame:
    """Drop duplicate timestamps, keeping first/last occurrence."""
    if TS_SEC not in df.columns:
        return df
    return df.drop_duplicates(subset=[TS_SEC], keep=keep)


def deduplicate(df: pd.DataFrame, keep: str = "first") -> pd.DataFrame:
    """Drop fully duplicated rows (sensor level) plus duplicate timestamps."""
    out = df.drop_duplicates(keep=keep)
    return drop_duplicate_timestamps(out, keep=keep)


def ensure_monotonic(df: pd.DataFrame) -> pd.DataFrame:
    """Sort rows by timestamp and reset the index."""
    if TS_SEC not in df.columns:
        return df
    out = df.sort_values(TS_SEC).reset_index(drop=True)
    return out


def clamp_gnss(
    df: pd.DataFrame,
    lat_min: float = -90.0,
    lat_max: float = 90.0,
    lon_min: float = -180.0,
    lon_max: float = 180.0,
) -> pd.DataFrame:
    """Remove out-of-range lat/lon fixes (NaNs them)."""
    out = df.copy()
    for col, lo, hi in (
        (GNSS_LAT, lat_min, lat_max),
        (GNSS_LON, lon_min, lon_max),
    ):
        if col in out.columns:
            out[col] = out[col].where((out[col] >= lo) & (out[col] <= hi))
    return out


def zero_gravity_offset(df: pd.DataFrame) -> pd.DataFrame:
    """Subtract the stationary gravity vector baseline from accel axes.

    IO-VNBD accelerometer data includes gravity. This removes the dominant
    baseline so downstream features see dynamic acceleration. Uses the mean of
    the lowest-acceleration percentile of the recording as the static baseline
    when a nonzero reference is not supplied (kept simple for v1).
    """
    out = df.copy()
    if not {ACCEL_X, ACCEL_Y, ACCEL_Z}.issubset(out.columns):
        return out
    acc = out[[ACCEL_X, ACCEL_Y, ACCEL_Z]].abs().mean(axis=1)
    out["_acc_mag"] = acc
    # static baseline = mean of the 10% lowest |acc| samples
    k = max(1, int(len(out) * 0.10))
    idx = acc.nsmallest(k).index
    base = out.loc[idx, [ACCEL_X, ACCEL_Y, ACCEL_Z]].mean()
    for c in (ACCEL_X, ACCEL_Y, ACCEL_Z):
        out[c] = out[c] - base[c]
    out = out.drop(columns=["_acc_mag"])
    return out


def clean_trip(
    df: pd.DataFrame,
    drop_na: bool = True,
    dedupe: bool = True,
    sort_by_time: bool = True,
    clamp: bool = True,
) -> pd.DataFrame:
    """Convenience wrapper applying the Standard cleaning order."""
    out = df.copy()
    if drop_na:
        out = drop_na_rows(out)
    if dedupe:
        out = deduplicate(out)
    if sort_by_time:
        out = ensure_monotonic(out)
    if clamp:
        out = clamp_gnss(out)
    return out