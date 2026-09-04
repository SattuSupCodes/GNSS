"""Tests for gravity estimation (src/calibration/gravity_estimation.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.calibration.gravity_estimation import (
    GravityEstimator,
    STANDARD_GRAVITY,
    check_gravity_tolerance,
    estimate_gravity_static,
    gravity_magnitude_stats,
)


def _flat_frame(n=121, g=(0.0, 0.0, 9.8), noise=0.05, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "timestamp": 1600000000.0 + np.arange(n) / 10.0,
            "accel_x": np.full(n, g[0]) + rng.normal(0.0, noise, n),
            "accel_y": np.full(n, g[1]) + rng.normal(0.0, noise, n),
            "accel_z": np.full(n, g[2]) + rng.normal(0.0, noise, n),
        }
    )


def test_lowpass_recovers_gravity_magnitude():
    df = _flat_frame()
    res = GravityEstimator().fit_transform(df)
    assert res.status == "ok"
    mag = res.frame["gravity_est_magnitude"]
    assert np.nanmean(mag) == pytest.approx(STANDARD_GRAVITY, abs=0.1)
    assert res.frame["accel_x"].equals(df["accel_x"])  # raw never touched


def test_mean_method_averages_each_axis():
    df = _flat_frame(g=(1.0, 2.0, 9.5))
    res = GravityEstimator(method="mean").fit_transform(df)
    assert np.nanmean(res.frame["gravity_est_x"]) == pytest.approx(1.0, abs=0.05)
    assert np.nanmean(res.frame["gravity_est_y"]) == pytest.approx(2.0, abs=0.05)
    assert np.nanmean(res.frame["gravity_est_z"]) == pytest.approx(9.5, abs=0.05)


def test_linear_accel_is_residual():
    df = _flat_frame()
    res = GravityEstimator().fit_transform(df)
    lin = res.frame["linear_accel_x"] - 0.0
    assert np.allclose(res.frame["accel_x"], res.frame["gravity_est_x"] + lin)


def test_insufficient_samples_reports_status():
    df = _flat_frame(n=5)
    res = GravityEstimator(min_samples=20).fit_transform(df)
    assert res.status == "insufficient_samples"
    assert res.frame["gravity_est_valid"].isna().all() or not res.frame["gravity_est_valid"].any()


def test_raw_column_preserved_and_new_columns_added():
    df = _flat_frame()
    res = GravityEstimator().fit_transform(df)
    for c in ("gravity_est_x", "gravity_est_y", "gravity_est_z",
              "gravity_est_magnitude", "linear_accel_x", "linear_accel_y",
              "linear_accel_z", "gravity_est_valid"):
        assert c in res.frame.columns


def test_nan_gap_not_fabricated():
    df = _flat_frame(n=80)
    df.loc[30:50, "accel_x"] = np.nan
    res = GravityEstimator().fit_transform(df)
    gap = res.frame.loc[30:50, "gravity_est_x"]
    assert gap.isna().all()


def test_missing_columns_status():
    res = GravityEstimator().fit_transform(pd.DataFrame({"timestamp": [0.0]}))
    assert res.status == "missing_columns"


def test_static_vector():
    g, mag = estimate_gravity_static(np.tile([1.0, 2.0, 9.0], (40, 1)))
    assert mag == pytest.approx(np.linalg.norm([1.0, 2.0, 9.0]))
    assert np.allclose(g, [1.0, 2.0, 9.0])


def test_empty_static_window_returns_none():
    g, mag = estimate_gravity_static(np.empty((0, 3)))
    assert g is None and mag is None


def test_gravity_stats_and_tolerance():
    gx, gy, gz = np.zeros(50), np.zeros(50), np.full(50, 9.8)
    stats = gravity_magnitude_stats(gx, gy, gz)
    assert stats["n_valid"] == 50
    assert stats["pct_within_tol"] == 1.0
    assert check_gravity_tolerance(gx, gy, gz)
    assert not check_gravity_tolerance([np.nan], [np.nan], [np.nan])