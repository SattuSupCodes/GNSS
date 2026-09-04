"""Signal filtering for IMU channels.

Applies noise-reduction filters to canonical IMU columns. All filters operate
axis-wise and preserve the frame structure and index. Requires ``scipy``.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

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


def _require_scipy():
    try:
        import scipy  # noqa: F401
    except ImportError:
        raise ImportError("scipy is required for filtering; run `pip install scipy`")


def butter_lowpass(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    cutoff_hz: float = 4.0,
    fs: float = 10.0,
    order: int = 4,
) -> pd.DataFrame:
    """Zero-phase low-pass Butterworth filter on the given IMU columns."""
    _require_scipy()
    from scipy.signal import butter, filtfilt

    cols = columns or IMU_COLUMNS
    cols = [c for c in cols if c in df.columns]
    out = df.copy()
    nyq = fs / 2.0
    if cutoff_hz >= nyq:
        raise ValueError(
            f"cutoff_hz ({cutoff_hz}) must be below Nyquist ({nyq:.2f})"
        )
    b, a = butter(order, cutoff_hz / nyq, btype="low")
    for c in cols:
        vals = out[c].to_numpy(dtype=float)
        if vals.size > order * 3 and np.isfinite(vals).all():
            out[c] = filtfilt(b, a, vals)
    return out


def savgol_filter(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    window_length: int = 15,
    polyorder: int = 3,
) -> pd.DataFrame:
    """Savitzky-Golay smoothing on the given IMU columns."""
    _require_scipy()
    from scipy.signal import savgol_filter as _sg

    cols = columns or IMU_COLUMNS
    cols = [c for c in cols if c in df.columns]
    if window_length % 2 == 0:
        raise ValueError("window_length must be odd")
    if polyorder >= window_length:
        raise ValueError("polyorder must be < window_length")
    out = df.copy()
    for c in cols:
        vals = out[c].to_numpy(dtype=float)
        if vals.size > window_length and np.isfinite(vals).all():
            out[c] = _sg(vals, window_length, polyorder)
    return out


def median_filter(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
    window_length: int = 5,
) -> pd.DataFrame:
    """Moving median filter (robust to outliers) on IMU columns."""
    _require_scipy()
    from scipy.ndimage import median_filter as _med

    cols = columns or IMU_COLUMNS
    cols = [c for c in cols if c in df.columns]
    out = df.copy()
    for c in cols:
        vals = out[c].to_numpy(dtype=float)
        if vals.size > window_length and np.isfinite(vals).all():
            out[c] = _med(vals, size=window_length, mode="nearest")
    return out