import math

import numpy as np
import pandas as pd
import pytest

from src.navigation.interfaces.messages import (
    GNSSSample,
    IMUSample,
    MLNavigationOutput,
)
from src.navigation.map_matching.map_matcher import RoadCandidate
from src.navigation.engine.idr_engine import IDREngine
from src.engine.engine_trip_runner import (
    build_engine,
    print_engine_report,
    run_fusion,
)
from src.navigation.confidence.confidence import ConfidenceEstimator

LAT0, LON0 = 52.5, -1.9


@pytest.fixture
def engine():
    return IDREngine()


def imu(t, ax=0.0, ay=0.0, gz=0.0):
    return IMUSample(
        timestamp=t,
        accelerometer=(ax, ay, 0.0),
        gyroscope=(0.0, 0.0, gz),
        linear_acceleration_enu=(ax, ay),
    )


def gps(t, lat=LAT0, lon=LON0, acc=3.0, speed=None, heading=None):
    return GNSSSample(
        timestamp=t,
        latitude=lat,
        longitude=lon,
        accuracy=acc,
        speed=speed,
        heading=heading,
    )


def test_initialize_and_first_gnss(engine):
    engine.update_gnss(gps(0.0))
    state = engine.get_state()
    assert state.latitude == pytest.approx(LAT0, abs=1e-6)
    assert state.mode == "GNSS_INS_FUSION"


def test_state_dict_has_api_keys(engine):
    engine.update_gnss(gps(0.0))
    engine.update_imu(imu(0.1))
    d = engine.get_state_dict()
    for key in (
        "timestamp",
        "latitude",
        "longitude",
        "velocity",
        "heading",
        "confidence",
        "position_error",
        "mode",
        "east_m",
        "north_m",
        "velocity_east_mps",
        "velocity_north_mps",
    ):
        assert key in d
    assert d["latitude"] is not None
    assert d["longitude"] is not None


def test_heading_and_speed_via_ml(engine):
    # Push a 90-degree heading (East) then a speed; the at-rest speed update
    # projects velocity along the filter's (updated) heading.
    engine.update_gnss(gps(0.0))
    engine.update_ml(MLNavigationOutput(timestamp=0.1, heading_rad=math.pi / 2))
    engine.update_ml(
        MLNavigationOutput(timestamp=0.15, speed_mps=5.0, heading_rad=math.pi / 2)
    )
    state = engine.get_state()
    speed = (state.velocity_east_mps ** 2 + state.velocity_north_mps ** 2) ** 0.5
    assert speed == pytest.approx(5.0, abs=1.5)
    # After a 90-degree turn toward East + speed, velocity is predominantly east.
    assert state.velocity_east_mps > 2.5
    assert abs(state.heading_rad - math.pi / 2) < 0.4


def test_outage_drops_mode_to_dead_reckoning(engine):
    engine.update_gnss(gps(0.0))
    engine.update_imu(imu(0.1))
    # Feed silent now: gap 5 s > max_gap 3 s.
    engine.update_imu(imu(5.0))
    assert engine.mode == "DEAD_RECKONING"
    assert engine.get_state().confidence < 1.0


def test_confidence_degrades_with_gnss_age():
    conf = ConfidenceEstimator(drift_rate_mps=0.5)
    c_fresh = conf.estimate(2.0, "GNSS_INS_FUSION", gnss_age_s=0.0)
    c_stale = conf.estimate(2.0, "GNSS_INS_FUSION", gnss_age_s=30.0)
    assert c_stale < c_fresh


def test_map_match_correction(engine):
    engine.update_gnss(gps(0.0))
    candidates = [
        RoadCandidate(road_id="r0", east_m=50.0, north_m=0.0, heading_rad=0.0, distance_m=0.0)
    ]
    for _ in range(12):
        engine.update_map_match(candidates=candidates)
    state = engine.get_state()
    # Soft re-localization pulls the estimate toward the matched road; each
    # update moves partway, converging asymptotically toward 50 m.
    assert state.east_m > 40.0
    assert state.east_m < 50.0


def test_non_holonomic_suppresses_lateral_velocity(engine):
    engine.update_gnss(gps(0.0))
    engine.update_ml(MLNavigationOutput(timestamp=0.1, speed_mps=5.0, heading_rad=0.0))
    state = engine.get_state()
    assert state.velocity_north_mps > 3.0
    engine.apply_non_holonomic_constraint()
    assert abs(engine.get_state().velocity_east_mps) < 0.5


def test_zupt_zeroes_velocity(engine):
    engine.update_gnss(gps(0.0))
    engine.update_ml(MLNavigationOutput(timestamp=0.1, speed_mps=5.0, heading_rad=0.0))
    engine.apply_zupt()
    assert engine.get_state().velocity_east_mps == pytest.approx(0.0, abs=0.1)
    assert engine.get_state().velocity_north_mps == pytest.approx(0.0, abs=0.1)


def test_ukf_engine_build_and_run():
    engine = build_engine({"engine": {"filter_type": "ukf"}})
    engine.update_gnss(gps(0.0))
    engine.update_imu(imu(0.1))
    assert engine.get_state().mode in ("GNSS_INS_FUSION", "DEAD_RECKONING")
    assert np.isfinite(engine.get_state().east_m)


# ---------------------------------------------------------------------- #
# Dataframe-level runner
# ---------------------------------------------------------------------- #


def _synthetic_trip_df(n=30):
    ts = 1600000000.0 + np.arange(n) / 10.0
    north = 0.5 * 0.5 * (np.arange(n) / 10.0) ** 2  # const 0.5 m/s^2
    vel = 0.5 * np.arange(n) / 10.0
    lat = LAT0 + north / 111_320.0
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "linear_accel_x": rng.normal(0.0, 0.05, n),
            "linear_accel_y": np.full(n, 0.5),
            "linear_accel_z": np.zeros(n),
            "gyro_z": np.zeros(n),
            "orient_qw": np.ones(n),
            "orient_qx": np.zeros(n),
            "orient_qy": np.zeros(n),
            "orient_qz": np.zeros(n),
            "latitude_deg": lat,
            "longitude_deg": np.full(n, LON0),
            "speed_kmh": vel * 3.6,
            "gps_heading_deg": np.zeros(n),
            "position_accuracy_m": np.full(n, 3.0),
            "reference_latitude_deg": lat,
            "reference_longitude_deg": np.full(n, LON0),
        }
    )


def test_run_fusion_over_dataframe():
    result = run_fusion(_synthetic_trip_df(), {})
    assert len(result.trajectory) > 0
    assert {"east_m", "north_m", "heading", "latitude"} <= set(result.trajectory.columns)
    assert result.position_rmse_m < 20.0

    import io as _io

    print_engine_report(result)
    assert result.final_state.mode in ("GNSS_INS_FUSION", "DEAD_RECKONING")


def test_run_fusion_respects_blackout_mask():
    df = _synthetic_trip_df()
    df.loc[10:20, "latitude_deg"] = np.nan
    df.loc[10:20, "longitude_deg"] = np.nan
    df.loc[10:20, "gnss_available"] = 0.0
    result = run_fusion(df, {})
    assert len(result.trajectory) > 0