"""Tests for the full calibration pipeline."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.calibration.calibration_pipeline import CalibrationConfig, CalibrationPipeline
from src.calibration.sensor_calibration import SOURCE_CONFIGURED, SOURCE_ESTIMATED


def _trip(n=121, trip_id="vw_test", seed=11):
    rng = np.random.default_rng(seed)
    ts = 1600000000.0 + np.arange(n) / 10.0
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "accel_x": rng.normal(0.1, 0.2, n),
            "accel_y": rng.normal(0.0, 0.2, n),
            "accel_z": rng.normal(9.8, 0.2, n),
            "gyro_x": rng.normal(0.0, 0.02, n),
            "gyro_y": rng.normal(0.0, 0.02, n),
            "gyro_z": rng.normal(0.0, 0.02, n),
            "mag_x": rng.normal(0.0, 0.5, n),
            "mag_y": rng.normal(25.0, 0.5, n),
            "mag_z": rng.normal(-35.0, 0.5, n),
            "latitude_deg": np.where(np.arange(n) % 20 == 0, 52.5, np.nan),
            "longitude_deg": np.where(np.arange(n) % 20 == 0, -1.9, np.nan),
            "speed_kmh": np.where(np.arange(n) % 20 == 0, 40.0, np.nan),
            "trip_id": np.full(n, trip_id),
            "source_file": np.full(n, "data/raw/S-vw16b.csv"),
            "sync_status": np.full(n, "synchronised"),
        }
    )
    return df


def test_pipeline_preserves_raw_columns():
    df = _trip()
    res = CalibrationPipeline(CalibrationConfig()).run(df)
    for c in ("accel_x", "accel_z", "gyro_x", "mag_y", "timestamp",
              "speed_kmh", "trip_id", "source_file", "sync_status", "latitude_deg"):
        assert c in res.frame.columns, c
        pd.testing.assert_series_equal(res.frame[c], df[c])


def test_pipeline_adds_all_phase2_columns():
    df = _trip()
    res = CalibrationPipeline(CalibrationConfig()).run(df)
    expected_prefixes = ("gravity_est_", "linear_accel_", "orient_",
                         "accel_", "gyro_", "mag_", "category", "driver")
    for col in res.added_columns:
        assert any(col.startswith(p) for p in expected_prefixes), col
    assert "gravity_est_magnitude" in res.frame.columns
    assert "orient_yaw_deg" in res.frame.columns
    assert "accel_x_cal" in res.frame.columns
    assert "accel_x_aligned" in res.frame.columns
    assert "orient_heading_source" in res.frame.columns


def test_pipeline_metadata_is_serialisable_and_reports():
    df = _trip()
    res = CalibrationPipeline(CalibrationConfig()).run(df)
    assert res.status == "ok"
    assert "gravity" in res.metadata and "alignment" in res.metadata
    assert res.metadata["alignment"]["world_frame"] == "ENU"
    json.dumps(res.metadata)  # must be serialisable
    assert res.metadata["sensor_availability"]["accel"] == 1.0


def test_pipeline_uses_configured_identity_profiles_by_default():
    df = _trip()
    res = CalibrationPipeline(CalibrationConfig()).run(df)
    profiles = res.metadata["calibration"]["profiles"]
    for sensor in ("accel", "gyro", "mag"):
        assert profiles[sensor]["source"] == SOURCE_CONFIGURED
        assert profiles[sensor]["scale"] == [1.0, 1.0, 1.0]
        assert profiles[sensor]["bias"] == [0.0, 0.0, 0.0]


def test_pipeline_derives_category_from_source_file():
    df = _trip()
    res = CalibrationPipeline(CalibrationConfig()).run(df)
    assert "category" in res.frame.columns
    assert res.frame["category"].iloc[0] == "VW"


def test_pipeline_estimates_gyro_bias_from_rest():
    df = _trip()
    cfg = CalibrationConfig(calibrate_gyro=True, estimate_gyro_bias_from_rest=False)
    rng = np.random.default_rng(0)
    rest = rng.normal([0.2, -0.1, 0.0], 0.005, size=(100, 3))
    res = CalibrationPipeline(cfg).run(df, gyro_rest_samples=rest)
    prof = res.metadata["calibration"]["profiles"]["gyro"]
    assert prof["source"] == SOURCE_ESTIMATED
    assert abs(prof["bias"][0] - 0.2) < 0.03
    middle = res.frame["gyro_x_cal"].iloc[60]
    assert abs(middle - (df["gyro_x"].iloc[60] - 0.2)) < 0.03


def test_pipeline_rest_requested_but_unavailable_stays_configured():
    df = _trip()
    cfg = CalibrationConfig(calibrate_gyro=True)  # rest requested, no samples
    res = CalibrationPipeline(cfg).run(df)
    prof = res.metadata["calibration"]["profiles"]["gyro"]
    assert prof["source"] == "configured"
    assert prof["bias"] == [0.0, 0.0, 0.0]
    # gyro_cal columns are honest copies of raw
    assert np.allclose(res.frame["gyro_x_cal"], df["gyro_x"].to_numpy())


def test_pipeline_custom_alignment_rotates_aligned_columns():
    df = _trip()
    cfg = CalibrationConfig(
        alignment_yaw_deg=-90.0, alignment_pitch_deg=0.0, alignment_roll_deg=0.0
    )
    res = CalibrationPipeline(cfg).run(df)
    # a device-frame -Y(ish) accel read should become positive-X (East) aligned
    aligned_x = res.frame["accel_x_aligned"].to_numpy()
    assert np.mean(aligned_x) != pytest.approx(np.mean(df["accel_x"]), abs=0.05)


def test_pipeline_keeps_nan_rows_in_estimated_columns():
    df = _trip()
    n = len(df)
    df.loc[n // 2 - 3 : n // 2 + 3, ["accel_x", "accel_y", "accel_z"]] = np.nan
    res = CalibrationPipeline(CalibrationConfig()).run(df)
    gap = res.frame.loc[n // 2 - 2 : n // 2 + 2, "accel_x_aligned"]
    assert gap.isna().any()