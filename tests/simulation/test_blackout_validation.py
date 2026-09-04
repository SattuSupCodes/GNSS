"""Tests for the blackout data-quality validation utility."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data.blackout_validation import (
    validate_blackout_frame,
    validate_trip_frame,
)
from src.preprocessing.synchronization import ffill_gnss
from src.simulation.gnss_blackout import GNSS_FIELDS, apply_blackout, plan_blackout_intervals


@pytest.fixture
def trip():
    n = 121
    ts = 1600000000.0 + np.arange(n) / 10.0
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "datetime": pd.to_datetime(ts, unit="s"),
            "accel_x": np.ones(n),
            "accel_y": np.ones(n),
            "accel_z": np.full(n, 9.8),
            "gyro_x": np.zeros(n),
            "gyro_y": np.zeros(n),
            "gyro_z": np.zeros(n),
            "mag_x": np.ones(n),
            "mag_y": np.ones(n),
            "mag_z": np.ones(n),
            "gravity_z": np.full(n, 9.8),
            "orientation_roll_deg": np.zeros(n),
            "accel_x_cal": np.ones(n),
            "accel_y_cal": np.ones(n),
            "accel_z_cal": np.ones(n),
            "latitude_deg": np.where(np.arange(n) % 20 == 0, 52.5, np.nan),
            "longitude_deg": np.where(np.arange(n) % 20 == 0, -1.9, np.nan),
            "altitude_m": np.where(np.arange(n) % 20 == 0, 90.0, np.nan),
            "speed_kmh": np.where(np.arange(n) % 20 == 0, 40.0, np.nan),
            "position_accuracy_m": np.where(np.arange(n) % 20 == 0, 3.0, np.nan),
            "gps_heading_deg": np.where(np.arange(n) % 20 == 0, 90.0, np.nan),
            "gps_satellites": np.where(np.arange(n) % 20 == 0, 12.0, np.nan),
            "trip_id": np.array(["vw_test"] * n),
        }
    )
    return ffill_gnss(df)


@pytest.fixture
def blackout(trip):
    intervals = plan_blackout_intervals(
        trip["timestamp"], duration_s=5.0, seed=7, trip_id="vw_test"
    )
    return apply_blackout(trip, intervals).frame


def test_validate_passes_on_clean(trip, blackout):
    report = validate_blackout_frame(
        trip, blackout,
        mask_columns=GNSS_FIELDS,
        availability_column="gnss_available",
        phase_column="blackout_phase",
        blackout_id_column="blackout_id",
    )
    assert report.ok, report.summary()


def test_fails_row_count_changed(trip, blackout):
    changed = blackout.iloc[:-1]
    report = validate_blackout_frame(trip, changed, availability_column="gnss_available")
    assert not report.ok
    assert any(i.check == "rows" and i.status == "fail" for i in report.issues)


def test_fails_gnss_inside_not_nan(trip, blackout):
    bad = blackout.copy()
    bad.loc[~bad["gnss_available"], "latitude_deg"] = 52.5  # "silently fixed"
    report = validate_blackout_frame(trip, bad, mask_columns=GNSS_FIELDS,
                                     availability_column="gnss_available")
    assert not report.ok
    assert any(i.check.startswith("gnss_field::") and i.status == "fail" for i in report.issues)


def test_fails_modified_column(trip, blackout):
    bad = blackout.copy()
    bad.loc[0, "accel_x"] = 999.0
    report = validate_blackout_frame(trip, bad, availability_column="gnss_available")
    assert not report.ok
    assert any(i.check == "preserved_columns" and i.status == "fail" for i in report.issues)


def test_fails_non_monotonic_timestamps(trip, blackout):
    bad = blackout.copy()
    bad = bad.sample(frac=1.0, random_state=0).reset_index(drop=True)
    bad["timestamp"] = bad["timestamp"].values[::-1]
    report = validate_blackout_frame(trip, bad, availability_column="gnss_available")
    assert not report.ok


def test_fails_duplicate_timestamps(trip, blackout):
    bad = blackout.copy()
    bad.loc[1, "timestamp"] = bad.loc[0, "timestamp"]
    report = validate_blackout_frame(trip, bad, availability_column="gnss_available")
    assert not report.ok
    assert any(i.check == "timestamp_duplicates" and i.status == "fail" for i in report.issues)


def test_availability_phase_disagreement_fails(trip, blackout):
    bad = blackout.copy()
    first_masked = bad.index[~bad["gnss_available"]][0]
    bad.loc[first_masked, "blackout_phase"] = "pre_blackout"
    report = validate_blackout_frame(trip, bad, availability_column="gnss_available",
                                     phase_column="blackout_phase")
    assert not report.ok
    assert any(i.check == "availability_phase" and i.status == "fail" for i in report.issues)


def test_report_assert_ok_raises(trip, blackout):
    bad = blackout.iloc[:-1]
    report = validate_blackout_frame(trip, bad, availability_column="gnss_available")
    with pytest.raises(AssertionError):
        report.assert_ok(reason="raw check")


def test_trip_frame_validator_missing_sensor_fails():
    df = pd.DataFrame({"timestamp": [1.0, 2.0, 3.0], "accel_x": [1.0, 2.0, 3.0]})
    report = validate_trip_frame(df)
    assert not report.ok
    assert any(i.check == "sensor_columns" and i.status == "fail" for i in report.issues)


def test_trip_frame_validator_ok_on_clean(trip):
    report = validate_trip_frame(trip)
    assert report.ok, report.summary()