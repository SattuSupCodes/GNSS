"""Tests for signal filtering."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.preprocessing.filtering import (
    butter_lowpass,
    median_filter,
    savgol_filter,
)


def test_butter_lowpass_reduces_noise_variance(canonical_trip):
    df = canonical_trip.copy()
    out = butter_lowpass(df, cutoff_hz=2.0, fs=10.0, order=2)
    assert out["accel_x"].var() < df["accel_x"].var()


def test_butter_lowpass_rejects_cutoff_at_nyquist(canonical_trip):
    with pytest.raises(ValueError):
        butter_lowpass(canonical_trip, cutoff_hz=5.0, fs=10.0)


def test_savgol_keeps_shape(canonical_trip):
    df = canonical_trip.copy()
    out = savgol_filter(df, window_length=15, polyorder=3)
    assert len(out) == len(df)
    # smoothing a noisy sine-ish column reduces variance
    assert out["gyro_x"].var() < df["gyro_x"].var()


def test_savgol_requires_odd_window(canonical_trip):
    with pytest.raises(ValueError):
        savgol_filter(canonical_trip, window_length=16)


def test_median_filter_removes_impulse(canonical_trip):
    df = canonical_trip.copy()
    df.loc[10, "accel_x"] = 500.0  # gross spike
    out = median_filter(df, window_length=5)
    assert abs(out.loc[10, "accel_x"]) < 100.0


def test_filters_leave_metadata_intact(canonical_trip):
    out = butter_lowpass(canonical_trip)
    assert "trip_id" in out.columns