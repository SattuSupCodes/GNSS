"""Tests for blackout dataset assembly (reference attach, runtime/reference split)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.simulation.blackout_dataset import (
    REFERENCE_PREFIX,
    create_blackout_dataset,
)
from src.simulation.blackout_scenarios import build_scenarios
from src.simulation.config import EvaluationConfig

REPO_REF_COLS = {
    "reference_latitude_deg": " Latitude (degrees)",
    "reference_longitude_deg": " Longitude (degrees)",
    "reference_speed_kmh": " Velocity (km/hr)",
    "reference_heading_deg": " Heading (degrees)",
    "reference_height_m": " Height (km)",
}


@pytest.fixture
def frame():
    n = 200
    ts = 1600000000.0 + np.arange(n) / 10.0
    rng = np.random.default_rng(3)
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "accel_x": rng.normal(0.1, 0.2, n),
            "accel_y": rng.normal(0.0, 0.2, n),
            "accel_z": rng.normal(9.8, 0.2, n),
            "gyro_x": np.zeros(n),
            "gyro_y": np.zeros(n),
            "gyro_z": np.zeros(n),
            "latitude_deg": np.linspace(52.50, 52.60, n),  # dense GNSS
            "longitude_deg": np.linspace(-1.90, -1.85, n),
            "altitude_m": np.full(n, 90.0),
            "speed_kmh": np.full(n, 40.0),
            "position_accuracy_m": np.full(n, 3.0),
            "gps_heading_deg": np.full(n, 90.0),
            "gps_satellites": np.full(n, 12.0),
            "trip_id": "vw_test",
        }
    )
    return df


@pytest.fixture
def reference():
    n = 100
    return pd.DataFrame(
        {
            "timestamp": np.linspace(1600000000.0, 1600000000.0 + 19.9, n),
            " Latitude (degrees)": np.linspace(52.50, 52.60, n),
            " Longitude (degrees)": np.linspace(-1.90, -1.85, n),
            " Velocity (km/hr)": np.full(n, 41.0),
            " Heading (degrees)": np.full(n, 91.0),
            " Height (km)": np.full(n, 0.09),
        }
    )


def _cfg():
    return EvaluationConfig.from_dict(
        {
            "blackout": {
                "min_trip_duration_s": 5.0,
                "min_pre_blackout_s": 2.0,
                "min_post_blackout_s": 2.0,
            }
        }
    )


def test_create_with_reference_attaches_trajectory(frame, reference):
    scen = build_scenarios(["vw_test"], [5.0], seed=1)[0]
    ds = create_blackout_dataset(frame, scen, _cfg(), reference_df=reference)
    assert ds.has_reference
    assert ds.metadata()["has_reference"] is True
    ref = ds.frame["reference_latitude_deg"]
    assert ref.notna().sum() > 0
    assert ref.min() >= frame["latitude_deg"].min() - 1e-6
    assert ds.frame["reference_speed_kmh"].notna().all()
    assert (ds.frame["reference_source"] == "vehicle").all()


def test_create_without_reference_no_fabrication(frame):
    scen = build_scenarios(["vw_test"], [5.0], seed=1)[0]
    ds = create_blackout_dataset(frame, scen, _cfg(), reference_df=None)
    assert not ds.has_reference
    assert (ds.frame["reference_available"] == False).all()  # noqa: E712
    assert (ds.frame["reference_source"] == "none").all()
    for col in _cfg().reference.columns:
        assert ds.frame[col].isna().all()


def test_runtime_frame_excludes_reference(frame, reference):
    scen = build_scenarios(["vw_test"], [5.0], seed=1)[0]
    ds = create_blackout_dataset(frame, scen, _cfg(), reference_df=reference)
    runtime = ds.runtime_frame()
    assert not any(c.startswith(REFERENCE_PREFIX) for c in runtime.columns)
    assert "gnss_available" in runtime.columns
    assert "blackout_phase" in runtime.columns
    assert "accel_x" in runtime.columns


def test_reference_frame_only_timestamp_and_reference(frame, reference):
    scen = build_scenarios(["vw_test"], [5.0], seed=1)[0]
    ds = create_blackout_dataset(frame, scen, _cfg(), reference_df=reference)
    ref_fr = ds.reference_frame()
    expected = {"timestamp"} | {
        c for c in ds.frame.columns if c.startswith(REFERENCE_PREFIX)
    }
    assert set(ref_fr.columns) == expected


def test_metadata_contains_realization_info(frame, reference):
    scen = build_scenarios(["vw_test"], [5.0], seed=1)[0]
    ds = create_blackout_dataset(frame, scen, _cfg(), reference_df=reference)
    meta = ds.metadata()
    assert meta["scenario_id"] == scen.scenario_id
    assert meta["n_rows"] == len(frame)
    assert meta["realization"]["n_intervals"] == 1
    assert meta["realization"]["total_masked_samples"] > 0
    assert abs(meta["duration_s"] - 5.0) < 1e-9


def test_gnss_still_masked_when_reference_attached(frame, reference):
    scen = build_scenarios(["vw_test"], [5.0], seed=1)[0]
    ds = create_blackout_dataset(frame, scen, _cfg(), reference_df=reference)
    masked = ~ds.frame["gnss_available"]
    assert ds.frame.loc[masked, "latitude_deg"].isna().all()
    assert ds.frame.loc[~masked, "latitude_deg"].notna().all()