"""tests/ml/test_engine_integration.py - wiring through the navigation engine."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.navigation.interfaces.messages import MLNavigationOutput
from src.engine.engine_trip_runner import run_trip
from src.navigation.engine.idr_engine import IDREngine
from src.navigation.engine.model_interface import TrainedMLInference
from src.navigation.interfaces.messages import GNSSSample

from .conftest import needs_artifact

LAT0, LON0 = 52.5, -1.9
REPO = Path(__file__).resolve().parents[2]
SENSOR_COLS = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"]


def test_ml_error_floor_raised_through_engine():
    engine = IDREngine()
    engine.update_gnss(GNSSSample(timestamp=0.0, latitude=LAT0, longitude=LON0, accuracy=3.0))
    out = MLNavigationOutput(timestamp=0.1, position_error_m=50.0)
    engine.update_ml(out)
    state = engine.get_state()
    assert np.isfinite(state.position_error_m)
    assert state.position_error_m == pytest.approx(50.0)
    assert state.confidence < 1.0


def test_ml_error_floor_released_when_zero():
    # A zero/finite floor must not poison the reported error (regression:
    # previously the invalid NavigationState default of inf leaked through).
    engine = IDREngine()
    engine.update_gnss(GNSSSample(timestamp=0.0, latitude=LAT0, longitude=LON0, accuracy=3.0))
    engine.update_ml(MLNavigationOutput(timestamp=0.1, position_error_m=0.0))
    state = engine.get_state()
    assert np.isfinite(state.position_error_m)
    assert state.position_error_m == pytest.approx(engine.fusion.filter.position_std_m)


def test_empty_ml_output_runs_classically():
    engine = IDREngine()
    engine.update_gnss(GNSSSample(timestamp=0.0, latitude=LAT0, longitude=LON0, accuracy=3.0))
    engine.update_ml(MLNavigationOutput(timestamp=0.1))
    state = engine.get_state()
    assert np.isfinite(state.position_error_m)
    assert state.position_error_m == pytest.approx(engine.fusion.filter.position_std_m)


def test_accel_correction_accepted():
    engine = IDREngine()
    engine.update_gnss(GNSSSample(timestamp=0.0, latitude=LAT0, longitude=LON0, accuracy=3.0))
    out = MLNavigationOutput(
        timestamp=0.1,
        accel_correction_enu=(0.1, 0.5),
        accel_correction_std_mps2=1.0,
    )
    engine.update_ml(out)
    assert np.isfinite(engine.get_state().east_m)
    assert np.isfinite(engine.get_state().velocity_east_mps)


def _synthetic_nav_trip(n=400):
    rng = np.random.default_rng(7)
    ts = 1600000000.0 + np.arange(n) / 10.0
    north = 0.5 * 0.5 * (np.arange(n) / 10.0) ** 2
    lat = LAT0 + north / 111_320.0
    df = pd.DataFrame(
        {
            "timestamp": ts,
            "accel_x": rng.normal(0.0, 0.5, n),
            "accel_y": rng.normal(0.0, 0.5, n),
            "accel_z": np.full(n, 9.81),
            "gyro_x": rng.normal(0.0, 0.05, n),
            "gyro_y": rng.normal(0.0, 0.05, n),
            "gyro_z": rng.normal(0.0, 0.05, n),
            "accel_x_cal": 0.0,
            "accel_y_cal": 0.0,
            "accel_z_cal": 9.81,
            "gyro_x_cal": 0.0,
            "gyro_y_cal": 0.0,
            "gyro_z_cal": 0.0,
            "linear_accel_x": rng.normal(0.0, 0.05, n),
            "linear_accel_y": np.full(n, 0.5),
            "linear_accel_z": np.zeros(n),
            "orient_qw": np.ones(n),
            "orient_qx": np.zeros(n),
            "orient_qy": np.zeros(n),
            "orient_qz": np.zeros(n),
            "latitude_deg": lat,
            "longitude_deg": np.full(n, LON0),
            "speed_kmh": (0.5 * np.arange(n) / 10.0) * 3.6,
            "gps_heading_deg": np.zeros(n),
            "position_accuracy_m": np.full(n, 3.0),
            "gnss_available": np.ones(n),
            "reference_latitude_deg": lat,
            "reference_longitude_deg": np.full(n, LON0),
            "reference_speed_kmh": (0.5 * np.arange(n) / 10.0) * 3.6,
            "reference_heading_deg": np.zeros(n),
        }
    )
    return df


@needs_artifact("models/error_model.joblib")
def test_runner_feeds_corrections_on_imu_cadence():
    inf = TrainedMLInference()
    result = run_trip(_synthetic_nav_trip(), {}, ml_inference=inf)
    traj = result.trajectory
    assert len(traj) > 0
    # The correction hook writes learned outputs but must never degrade the
    # trajectory to NaN.
    assert np.isfinite(traj["east_m"]).all()
    assert np.isfinite(traj["position_error"]).all()
    assert (traj["position_error"] >= 0.0).all()
    # D-T5 error floor is actively finite (not nan / not all-zero when moving).
    assert float(traj["position_error"].max()) > 0.0


@needs_artifact("models/error_model.joblib")
def test_runner_survives_blackout_with_ml():
    path = REPO / "data" / "blackout" / "30s" / "s1__blk30s_00.parquet"
    if not path.exists():
        path = REPO / "data" / "blackout" / "30s" / "m__blk30s_00.parquet"
    if not path.exists():
        pytest.skip("blackout scenario parquet missing")
    df = pd.read_parquet(path)
    inf = TrainedMLInference()
    result = run_trip(df, {}, ml_inference=inf)
    traj = result.trajectory
    assert np.isfinite(traj["east_m"]).all()
    assert np.isfinite(traj["north_m"]).all()
    assert np.isfinite(traj["confidence"]).all()
    inner = traj[(traj["blackout_phase"] == "blackout")]
    assert len(inner) > 0
    # Position error remains finite and non-negative through the outage.
    assert np.isfinite(inner["position_error"]).all()
    assert (inner["position_error"] >= 0.0).all()