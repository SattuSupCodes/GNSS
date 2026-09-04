"""Column normalization for sensor channels.

Standardization (z-score) and min/max scaling for canonical IMU/GNSS columns.
Z-score parameters are computed from the training split only; this module
supports fitting on one frame and transforming another that way.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

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


def _present(df: pd.DataFrame, columns: List[str]) -> List[str]:
    return [c for c in columns if c in df.columns]


def fit_zscore(
    df: pd.DataFrame, columns: Optional[List[str]] = None
) -> Dict[str, Tuple[float, float]]:
    """Compute per-column (mean, std) z-score parameters from ``df``.

    Returns a dict mapping column name -> (mean, std). Only finite values are
    used for the statistics.
    """
    cols = _present(df, columns or IMU_COLUMNS)
    params: Dict[str, Tuple[float, float]] = {}
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(v) == 0:
            params[c] = (0.0, 1.0)
            continue
        params[c] = (float(v.mean()), float(v.std(ddof=0)))
    return params


def apply_zscore(
    df: pd.DataFrame, params: Dict[str, Tuple[float, float]]
) -> pd.DataFrame:
    """Apply pre-fitted z-score parameters to ``df``.

    Columns not present in ``params`` are left untouched. A std of 0 is
    protected (values stay as-is).
    """
    out = df.copy()
    for c, (mean, std) in params.items():
        if c not in out.columns:
            continue
        if std and np.isfinite(std):
            out[c] = (pd.to_numeric(out[c], errors="coerce") - mean) / std
    return out


def zscore(
    df: pd.DataFrame, columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """Fit z-score on the same frame and return the transformed frame."""
    return apply_zscore(df, fit_zscore(df, columns))


def fit_minmax(df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    """Per-column (min, max) parameters for min-max scaling."""
    cols = _present(df, IMU_COLUMNS)
    params: Dict[str, Tuple[float, float]] = {}
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(v) == 0:
            params[c] = (0.0, 1.0)
            continue
        params[c] = (float(v.min()), float(v.max()))
    return params


def apply_minmax(
    df: pd.DataFrame, params: Dict[str, Tuple[float, float]]
) -> pd.DataFrame:
    out = df.copy()
    for c, (lo, hi) in params.items():
        if c not in out.columns:
            continue
        v = pd.to_numeric(out[c], errors="coerce")
        rng = hi - lo
        if np.isfinite(rng) and rng > 0:
            out[c] = (v - lo) / rng
    return out


def minmax(df: pd.DataFrame) -> pd.DataFrame:
    """Fit min-max on the same frame and return the transformed frame."""
    return apply_minmax(df, fit_minmax(df))