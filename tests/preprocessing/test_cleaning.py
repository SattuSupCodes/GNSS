"""Tests for cleaning utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.preprocessing.cleaning import (
    clamp_gnss,
    clean_trip,
    drop_duplicate_timestamps,
    drop_na_rows,
    ensure_monotonic,
    zero_gravity_offset,
)


def test_drop_na_rows_removes_imu_nan(canonical_trip):
    df = canonical_trip.copy()
    df.loc[5, "accel_x"] = np.nan
    out = drop_na_rows(df)
    assert 5 not in out.index


def test_drop_duplicate_timestamps(canonical_trip):
    df = canonical_trip.copy()
    df = pd.concat([df.iloc[:2], df.iloc[:2]], ignore_index=True)
    out = drop_duplicate_timestamps(df)
    assert out["timestamp"].is_unique


def test_ensure_monotonic_sorts(canonical_trip):
    df = canonical_trip.sample(frac=1, random_state=0)
    out = ensure_monotonic(df)
    assert (out["timestamp"].diff().dropna() > 0).all()


def test_clamp_gnss_rejects_out_of_range(canonical_trip):
    df = canonical_trip.copy()
    df.loc[0, "latitude_deg"] = 120.0
    out = clamp_gnss(df)
    assert np.isnan(out.loc[0, "latitude_deg"])


def test_zero_gravity_offset_reduces_z_baseline(canonical_trip):
    df = canonical_trip.copy()
    out = zero_gravity_offset(df)
    # the static baseline removed most of the ~9.8 g offset on z
    assert abs(out["accel_z"].mean()) < abs(df["accel_z"].mean())


def test_clean_trip_is_well_formed(canonical_trip):
    out = clean_trip(canonical_trip)
    assert (out["timestamp"].diff().dropna() > 0).all()
    assert not out[["accel_x", "gyro_y"]].isna().any().any()


def test_clean_trip_preserves_metadata(canonical_trip):
    out = clean_trip(canonical_trip)
    assert "trip_id" in out.columns