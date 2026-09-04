"""Tests for sensor calibration utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.calibration.sensor_calibration import (
    SensorCalibrationProfile,
    SOURCE_CONFIGURED,
    SOURCE_ESTIMATED,
    SOURCE_UNAVAILABLE,
    apply_calibration,
    calibration_metadata_for,
    configured_profile,
    estimate_gyro_bias,
    fit_ellipsoid_scale_bias,
    fit_sphere_ls,
    unavailable_profile,
    validate_profile,
)


def test_configured_profile_applies_model():
    p = configured_profile("accel", bias=[1.0, -2.0, 0.5], scale=[1.0, 1.0, 1.0])
    out = p.calibrate(np.array([[2.0, 1.0, 3.0]]))
    assert np.allclose(out[0], [1.0, 3.0, 2.5])


def test_configured_profile_scale_requested():
    p = configured_profile("mag", scale=[2.0, 2.0, 2.0])
    out = p.calibrate(np.array([[1.0, 1.0, 1.0]]))
    assert np.allclose(out[0], [2.0, 2.0, 2.0])


def test_unavailable_profile_passes_through_without_nan():
    p = unavailable_profile("accel")
    assert not p.is_available()
    out = p.calibrate(np.array([[1.0, 2.0, 3.0]]))
    assert np.allclose(out[0], [1.0, 2.0, 3.0])


def test_validate_profile_rejects_zero_scale():
    p = SensorCalibrationProfile("accel", scale=np.array([0.0, 1.0, 1.0]))
    ok, reason = validate_profile(p)
    assert not ok and reason


def test_sphere_fit_recovers_bias():
    rng = np.random.default_rng(5)
    bias = np.array([0.3, -0.2, 0.1])
    # directions over a flattened cube + radius 9.8 (skip the zero vector)
    ticks = np.linspace(-1.0, 1.0, 9)
    dirs = np.array([[x, y, z] for x in ticks for y in ticks for z in ticks])
    dirs = dirs[np.linalg.norm(dirs, axis=1) > 0.5]
    dirs = dirs / np.linalg.norm(dirs, axis=1, keepdims=True)
    samples = bias + 9.8 * dirs + rng.normal(0.0, 0.02, dirs.shape)
    profile, report = fit_sphere_ls(samples, sensor="mag")
    assert report["ok"]
    assert profile.source == SOURCE_ESTIMATED
    assert np.allclose(profile.bias, bias, atol=0.1)
    assert profile.fitted_samples == len(samples)


def test_sphere_fit_insufficient_samples():
    profile, report = fit_sphere_ls(np.random.default_rng(0).normal(size=(4, 3)))
    assert profile is None
    assert report["reason"] == "insufficient_samples"


def test_ellipsoid_fit_shape():
    bias = np.array([0.2, -0.1, 0.3])
    scale = np.array([1.0, 1.3, 0.9])
    rng = np.random.default_rng(8)
    ticks = np.linspace(-1.0, 1.0, 7)
    dirs = np.array([[x, y, z] for x in ticks for y in ticks for z in ticks])
    dirs = dirs[np.linalg.norm(dirs, axis=1) > 0.5]
    dirs = dirs / np.linalg.norm(dirs, axis=1, keepdims=True)
    samples = bias + scale * dirs + rng.normal(0.0, 0.02, dirs.shape)
    profile, report = fit_ellipsoid_scale_bias(samples, sensor="accel")
    assert report["ok"]
    assert np.allclose(profile.bias, bias, atol=0.1)
    # scale rectifies the ellipsoid back to a unit sphere: scale_i ~ 1/radius_i
    # (rel. to scale_x = 1; global magnitude factor is not identifiable).
    rel = profile.scale / profile.scale[0]
    assert np.allclose(rel, [1.0, 1.0 / 1.3, 1.0 / 0.9], atol=0.15)


def test_gyro_bias_from_static_samples():
    rng = np.random.default_rng(2)
    static = rng.normal([0.1, -0.2, 0.05], 0.01, size=(100, 3))
    profile = estimate_gyro_bias(static)
    assert profile.source == SOURCE_ESTIMATED
    assert np.allclose(profile.bias, [0.1, -0.2, 0.05], atol=0.02)


def test_apply_calibration_appends_columns_and_keeps_raw():
    df = pd.DataFrame({
        "accel_x": [1.0, 2.0], "accel_y": [3.0, 4.0], "accel_z": [5.0, 6.0],
    })
    p = configured_profile("accel", bias=[1.0, 1.0, 1.0])
    out = apply_calibration(df, "accel", p)
    assert "accel_x_cal" in out.columns and "accel_y_cal" in out.columns
    assert out["accel_x"].tolist() == [1.0, 2.0]
    assert out["accel_x_cal"].tolist() == [0.0, 1.0]


def test_apply_calibration_requires_columns():
    df = pd.DataFrame({"accel_x": [1.0]})
    with pytest.raises(KeyError):
        apply_calibration(df, "accel", configured_profile("accel"))


def test_calibration_metadata_for_is_json_serialisable():
    import json

    profiles = {"accel": configured_profile("accel"), "mag": unavailable_profile("mag")}
    blob = calibration_metadata_for(profiles)
    json.dumps(blob)
    assert blob["accel"]["source"] == SOURCE_CONFIGURED
    assert blob["mag"]["source"] == SOURCE_UNAVAILABLE