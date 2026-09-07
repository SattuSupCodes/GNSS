import math

import numpy as np
import pytest

from src.navigation.fusion.gnss_ins_fusion import GNSSINSFusion
from src.navigation.fusion.ekf import EKF
from src.navigation.fusion.ukf import UKF
from src.navigation.health.gnss_health import GNSSHealthMonitor, GNSSMode

LAT0, LON0 = 52.5, -1.9


@pytest.fixture
def fusion():
    return GNSSINSFusion()


def test_initialize_sets_origin_and_filter(fusion):
    fusion.initialize(LAT0, LON0, heading_rad=0.0)
    assert fusion.initialized
    assert fusion.origin.initialized
    assert fusion.filter.x[0] == pytest.approx(0.0)


def test_predict_returns_dead_reckoning_without_gnss(fusion):
    fusion.initialize(LAT0, LON0)
    mode = fusion.predict_imu((0.0, 0.0), 0.0, 0.1, timestamp=0.1)
    assert mode == "DEAD_RECKONING"


def test_healthy_gnss_update(fusion):
    fusion.initialize(LAT0, LON0)
    fusion.predict_imu((0.0, 0.0), 0.0, 0.1, timestamp=0.1)
    mode, accepted, innovation = fusion.update_gnss(
        LAT0, LON0, accuracy=3.0, timestamp=0.2
    )
    assert mode == "GNSS_INS_FUSION"
    assert accepted is True
    assert innovation < 10.0


def test_first_gnss_initializes(fusion):
    mode, accepted, _ = fusion.update_gnss(LAT0, LON0, accuracy=3.0, timestamp=0.0)
    assert accepted
    assert mode == "GNSS_INS_FUSION"
    assert fusion.initialized


def test_degraded_accuracy_maps_to_gnss_ins_degraded(fusion):
    fusion.initialize(LAT0, LON0)
    fusion.predict_imu((0.0, 0.0), 0.0, 0.1, timestamp=0.1)
    mode, _, _ = fusion.update_gnss(LAT0, LON0, accuracy=15.0, timestamp=0.2)
    assert mode == "GNSS_INS_DEGRADED"


def test_outage_then_recovery(fusion):
    fusion.initialize(LAT0, LON0)
    fusion.update_gnss(LAT0, LON0, accuracy=3.0, timestamp=0.0)

    # Feed stops; IMU keeps running past the staleness window.
    fusion.predict_imu((0.0, 0.0), 0.0, 0.1, timestamp=5.0)
    assert fusion.mode == "DEAD_RECKONING"

    # First fix after the outage = recovering, then two more = healthy.
    mode, _, _ = fusion.update_gnss(LAT0, LON0, accuracy=3.0, timestamp=5.1)
    assert mode == "RECOVERING"

    mode, _, _ = fusion.update_gnss(LAT0, LON0, accuracy=3.0, timestamp=5.2)
    assert mode == "RECOVERING"

    mode, _, _ = fusion.update_gnss(LAT0, LON0, accuracy=3.0, timestamp=5.3)
    assert mode == "GNSS_INS_FUSION"


def test_soft_relocalization_inflates_uncertainty():
    re = 1.5
    fusion = GNSSINSFusion(re_localize_inflation=re)
    fusion.initialize(LAT0, LON0)
    fusion.health.mode = GNSSMode.UNAVAILABLE
    fusion.health.last_timestamp = None

    # Big innovation: filter is far away after the outage.
    fusion.filter.x[0] = 300.0
    fusion.filter.x[1] = 0.0
    fusion.predict_imu((0.0, 0.0), 0.0, 0.1, timestamp=10.0)
    _mode, accepted, innovation = fusion.update_gnss(
        LAT0, LON0, accuracy=3.0, timestamp=10.1
    )
    assert accepted
    assert innovation == pytest.approx(300.0, abs=5.0)


def test_re_localize_hard_correction(fusion):
    fusion.initialize(LAT0, LON0)
    fusion.predict_imu((0.0, 0.0), 0.0, 0.1, timestamp=0.1)
    for _ in range(3):
        fusion.re_localize(100.0, 100.0, std_m=1.0)
    assert fusion.filter.x[0] == pytest.approx(100.0, abs=2.0)
    assert fusion.filter.x[1] == pytest.approx(100.0, abs=2.0)


def test_to_state_fills_geography(fusion):
    fusion.initialize(LAT0, LON0)
    state = fusion.to_state(timestamp=1.0)
    assert state.latitude == pytest.approx(LAT0, abs=1e-6)
    assert state.longitude == pytest.approx(LON0, abs=1e-6)


def test_update_ml_speed_and_heading(fusion):
    fusion.initialize(LAT0, LON0)
    fusion.update_ml(speed_mps=5.0, heading_rad=0.0)
    assert fusion.filter.speed_mps == pytest.approx(5.0, abs=1.5)
    assert abs(fusion.filter.heading_rad) < 0.5


def test_ukf_fusion_buildable_and_tracks():
    fusion = GNSSINSFusion(filter_factory=UKF)
    fusion.initialize(LAT0, LON0)
    for i in range(5):
        fusion.predict_imu((0.1, 0.0), 0.0, 0.05, timestamp=0.05 * i)
        mode, accepted, _ = fusion.update_gnss(
            LAT0 + 0.00001 * i, LON0, accuracy=5.0, timestamp=0.05 * i + 0.025
        )
        assert accepted
    assert fusion.filter.x[0] > 0.0


def test_gnss_age(fusion):
    fusion.initialize(LAT0, LON0)
    fusion.update_gnss(LAT0, LON0, accuracy=3.0, timestamp=1.0)
    assert fusion.gnss_age(4.0) == pytest.approx(3.0)