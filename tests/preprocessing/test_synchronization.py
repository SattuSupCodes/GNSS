"""Tests for cross-source synchronization helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.preprocessing.synchronization import (
    align_to_grid,
    estimate_constant_offset,
    ffill_gnss,
    synchronize_vehicle_to_grid,
)


def test_ffill_gnss_fills_all_rows(canonical_trip):
    df = canonical_trip.copy()
    out = ffill_gnss(df)
    assert out["latitude_deg"].notna().all()
    # values before first fix stay NaN (forward fill semantics)
    first_fix = df["latitude_deg"].first_valid_index()
    before = df.loc[: first_fix - 1] if first_fix > 0 else df.iloc[:0]
    assert before.empty or before["latitude_deg"].isna().all()


def test_estimate_constant_offset_finds_shift():
    t = np.arange(0.0, 60.0, 0.1)
    signal = np.sign(np.sin(t / 2.0))  # distinct square-wave trace
    a = pd.DataFrame({"timestamp": t, "gps_heading_deg": signal})
    shift = 1.7  # b's timestamps are a's + 1.7 s
    b = pd.DataFrame({"timestamp": t + shift, "gps_heading_deg": signal})
    r = estimate_constant_offset(
        a, b, resolution=0.1, max_lag_seconds=5.0
    )
    # adding r to b's timestamps aligns b onto a -> r = -shift
    assert abs(r - (-shift)) < 0.2


def test_estimate_constant_offset_returns_zero_short_input():
    a = pd.DataFrame({"timestamp": [1.0, 2.0], "gps_heading_deg": [0.0, 0.0]})
    b = pd.DataFrame({"timestamp": [1.0, 2.0], "gps_heading_deg": [0.0, 0.0]})
    assert estimate_constant_offset(a, b) == 0.0


def test_align_to_grid_matches_grid_length(canonical_trip):
    grid = np.arange(1600000000.0, 1600000012.0, 0.1)
    out = align_to_grid(canonical_trip, grid)
    assert len(out) == len(grid)


def test_synchronize_vehicle_to_grid_is_reference_tagged(canonical_trip):
    grid = np.arange(1600000000.0, 1600000012.0, 0.2)
    ref = synchronize_vehicle_to_grid(canonical_trip, grid)
    assert (ref["is_reference"] == True).all()  # noqa: E712
    assert len(ref) == len(grid)