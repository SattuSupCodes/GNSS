"""Temporal resampling of a trip to a uniform time grid.

The IO-VNBD smartphone sampling is nominally 10 Hz but individual inter-sample
deltas jitter. This module resamples each channel onto a fixed-rate grid using
linear interpolation, which yields regular-length feature frames for the model.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

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
    MS_SINCE_START,
    TS_SEC,
)

INTERP_COLUMNS = [
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

# GNSS fields are sparse (a fix every few seconds). On the uniform grid we
# forward-fill these (hold the most recent fix), never linear-interpolate.
GNSS_HOLD_COLUMNS = [
    "latitude_deg",
    "longitude_deg",
    "altitude_m",
    "speed_kmh",
    "position_accuracy_m",
    "gps_heading_deg",
    "gps_satellites",
]

# Constant provenance columns carried through unchanged on the new grid.
META_HOLD_COLUMNS = ["trip_id", "source_file", "sync_status"]


def resample_uniform(
    df: pd.DataFrame,
    fs: float = 10.0,
    columns: Optional[Sequence[str]] = None,
    method: str = "linear",
) -> pd.DataFrame:
    """Resample ``df`` onto a uniform grid starting at its first timestamp.

    Parameters
    ----------
    fs : sampling rate in Hz.
    columns : sensor columns to interpolate (default: all IMU columns).
    method : interpolation method passed to :meth:`pandas.DataFrame.interpolate`.
        ``"linear"`` works on real data; ``"time"`` uses datetime index.

    Returns a new frame indexed 0..N-1 with a ``timestamp`` column on the grid
    and only the requested sensor columns. GNSS fields are dropped (they are
    too sparse to interpolate; synchronisation handles them separately).
    """
    if TS_SEC not in df.columns or len(df) < 2:
        return df.copy()
    out = df.copy()
    keep = list(columns) if columns is not None else INTERP_COLUMNS
    keep = [c for c in keep if c in out.columns]
    ghold = [c for c in GNSS_HOLD_COLUMNS if c in out.columns]
    # trim duplicate/irregular times then sort
    t = pd.to_numeric(out[TS_SEC], errors="coerce")
    out = out.loc[t.notna()].sort_values(TS_SEC)

    t0 = float(out[TS_SEC].iloc[0])
    t1 = float(out[TS_SEC].iloc[-1])
    n_new = int(np.floor((t1 - t0) * fs)) + 1
    grid = t0 + np.arange(n_new) / fs
    grid = grid[grid <= t1 + 1e-9]

    # Interpolate on float index using np.interp per column (cleaner than the
    # DataFrame.interpolate which needs a proper index).
    src_t = out[TS_SEC].to_numpy(dtype=float)
    resampled: dict = {TS_SEC: grid}
    for c in keep + ghold:
        vals = pd.to_numeric(out[c], errors="coerce").to_numpy(dtype=float)
        nan_mask = ~np.isfinite(vals)
        if nan_mask.all():
            resampled[c] = np.full(len(grid), np.nan)
            continue
        if c in ghold:
            # forward-fill the last known fix onto the grid
            filled = vals.copy()
            last = np.nan
            for i in range(len(filled)):
                if np.isfinite(filled[i]):
                    last = filled[i]
                else:
                    filled[i] = last
            resampled[c] = np.interp(grid, src_t, filled)
            continue
        if nan_mask.any():
            interp_base = np.interp(src_t, src_t[~nan_mask], vals[~nan_mask])
            vals = np.where(nan_mask, interp_base, vals)
        resampled[c] = np.interp(grid, src_t, vals)

    result = pd.DataFrame(resampled)
    for c in META_HOLD_COLUMNS:
        if c in out.columns:
            result[c] = out[c].iloc[-1]
    result[DATETIME] = pd.to_datetime(result[TS_SEC], unit="s", errors="coerce")
    if MS_SINCE_START in out.columns:
        src_ms = pd.to_numeric(out[MS_SINCE_START], errors="coerce").to_numpy()
        ms_mask = np.isfinite(src_ms)
        if ms_mask.any():
            result[MS_SINCE_START] = np.interp(
                grid, src_t[ms_mask], src_ms[ms_mask]
            )
    return result.reset_index(drop=True)