"""Temporal synchronization between data sources.

Two goals:
1. Cross-source alignment: smartphone IMU samples and vehicle CAN frames share
   a wall-clock timestamp but start at different offsets and may be offset by a
   constant. We estimate the constant offset via GNSS-context cross-correlation
   fallback and align onto the smartphone native grid.
2. Sparse-GNSS alignment: GNSS fixes arrive at ~1-10% of the IMU rate. We
   forward-fill each GNSS field onto the IMU timeline and mark with
   ``is_reference`` style provenance; the result is a frame where every row has
   an IMU sample and the best-known GNSS state.

The vehicle (V-*/*) files are REFERENCE ONLY and are never joined into the
smartphone runtime frame. They are returned separately for evaluation.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from ..data.data_schema import (
    GNSS_ACCURACY,
    GNSS_ALT,
    GNSS_HEADING,
    GNSS_LAT,
    GNSS_LON,
    GNSS_SATELLITES,
    GNSS_SPEED,
    TS_SEC,
)

GNSS_COLS = [
    GNSS_LAT,
    GNSS_LON,
    GNSS_ALT,
    GNSS_SPEED,
    GNSS_ACCURACY,
    GNSS_HEADING,
    GNSS_SATELLITES,
]


def estimate_constant_offset(
    a: pd.DataFrame,
    b: pd.DataFrame,
    a_fix_col: str = "timestamp",
    b_fix_col: str = "timestamp",
    a_trace_col: str = "gps_heading_deg",
    b_trace_col: Optional[str] = None,
    max_lag_seconds: float = 5.0,
    resolution: float = 0.1,
) -> float:
    """Estimate the constant time offset between two recordings of one route.

    When a and b record the same route (e.g. smartphone vs vehicle), their
    heading traces correlate. We resample each stream's raw trace onto the same
    absolute-time grid and cross-correlate; the lag maximizing correlation is
    the offset.

    Returns ``r`` such that **adding ``r`` to B's timestamps aligns B onto A**:

        a(t) ~= b(t + r)   after applying ``b_ts = b_ts + r``

    A positive ``r`` means B leads A in that applying the shift moves B later
    into alignment with A. Returns 0.0 when the data is insufficient.

    Parameters
    ----------
    a, b : frames with a monotonic time column and a trace (heading/speed) col.
    a_fix_col, b_fix_col : time columns of each frame.
    a_trace_col, b_trace_col : trace columns (b defaults to a's name).
    """
    if len(a) < 2 or len(b) < 2:
        return 0.0
    ta = pd.to_numeric(a[a_fix_col], errors="coerce")
    tb = pd.to_numeric(b[b_fix_col], errors="coerce")
    if not ta.notna().any() or not tb.notna().any():
        return 0.0

    bt = b_trace_col if b_trace_col is not None else a_trace_col

    def _raw_trace(df, fix_col, trace_col):
        t = pd.to_numeric(df[fix_col], errors="coerce")
        h = pd.to_numeric(df[trace_col], errors="coerce")
        m = t.notna() & h.notna()
        t, h = t[m].to_numpy(), h[m].to_numpy()
        if len(t) < 2:
            return None, None
        if "heading" in str(trace_col).lower():
            h = np.unwrap(np.deg2rad(h))
        order = np.argsort(t)
        return t[order], h[order]

    for hue_a, hue_b in ((a_trace_col, bt),):
        if hue_a is None or hue_b is None:
            continue
        if hue_a not in a.columns or hue_b not in b.columns:
            continue
        ta_h, sa = _raw_trace(a, a_fix_col, hue_a)
        tb_h, sb = _raw_trace(b, b_fix_col, hue_b)
        if ta_h is None or tb_h is None:
            continue
        lo, hi = max(ta_h.min(), tb_h.min()), min(ta_h.max(), tb_h.max())
        if hi - lo < 2.0:
            continue
        grid = np.arange(lo, hi, resolution)
        sa_r = np.interp(grid, ta_h, sa)
        sb_r = np.interp(grid, tb_h, sb)
        corr = np.correlate(sa_r - sa_r.mean(), sb_r - sb_r.mean(), mode="full")
        lags = np.arange(-(len(sa_r) - 1), len(sa_r)) * resolution
        sel = np.abs(lags) <= max_lag_seconds
        corr, lags = corr[sel], lags[sel]
        if not len(lags):
            continue
        best = int(np.argmax(np.abs(corr)))
        return float(lags[best])
    return 0.0


def align_to_grid(
    df: pd.DataFrame, grid: np.ndarray, columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """Align ``df`` rows onto an existing time grid via interpolation.

    Used to bring vehicle frames onto the smartphone grid for evaluation.
    """
    if TS_SEC not in df.columns or len(df) < 2:
        return df.copy()
    src_t = pd.to_numeric(df[TS_SEC], errors="coerce").to_numpy()
    m = np.isfinite(src_t)
    if not m.any():
        return df.copy()
    out = {TS_SEC: grid}
    cols = columns or [
        c for c in df.columns if c not in (TS_SEC, "datetime", "trip_id", "source_file", "sync_status", "is_reference")
    ]
    for c in cols:
        if c not in df.columns:
            continue
        v = pd.to_numeric(df[c], errors="coerce").to_numpy()
        finite = np.isfinite(v)
        if not finite.any():
            continue
        out[c] = np.interp(grid, src_t[m & finite], v[m & finite])
    result = pd.DataFrame(out)
    return result


def ffill_gnss(
    df: pd.DataFrame, columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """Forward-fill GNSS fixes onto every row so each IMU row also carries the
    best-known location fix."""
    cols = [c for c in (columns or GNSS_COLS) if c in df.columns]
    out = df.copy()
    out[cols] = out[cols].ffill()
    return out


def synchronize_smartphone(
    df: pd.DataFrame,
    offset_seconds: float = 0.0,
    ffill: bool = True,
) -> pd.DataFrame:
    """Apply a constant offset to the smartphone native grid and ffill GNSS."""
    out = df.copy()
    if TS_SEC in out.columns and offset_seconds:
        out[TS_SEC] = pd.to_numeric(out[TS_SEC], errors="coerce") + offset_seconds
    if ffill:
        out = ffill_gnss(out)
    return out


def synchronize_vehicle_to_grid(
    vehicle_df: pd.DataFrame,
    smartphone_ts: np.ndarray,
    columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Resample vehicle reference data onto the smartphone grid.

    Returns exclusively reference columns, every row tagged ``is_reference``.
    """
    aligned = align_to_grid(vehicle_df, smartphone_ts, columns=columns)
    aligned["is_reference"] = True
    return aligned