import math

import numpy as np
import pytest

from src.navigation.fusion.ekf import EKF
from src.navigation.fusion.state_model import (
    IDX_ACCEL_BIAS_E,
    IDX_ACCEL_BIAS_N,
    IDX_HEADING,
)


@pytest.fixture
def ekf():
    return EKF()


def test_initialize_sets_state(ekf):
    ekf.initialize(east=1.0, north=2.0, heading=math.pi / 2)
    assert ekf.x[0] == pytest.approx(1.0)
    assert ekf.x[1] == pytest.approx(2.0)
    assert ekf.heading_rad == pytest.approx(math.pi / 2)
    assert ekf.initialized


def test_predict_constant_accel_east(ekf):
    ekf.initialize(0.0, 0.0, heading=math.pi / 2)
    for _ in range(100):
        ekf.predict((1.0, 0.0), 0.0, 0.1)
    assert ekf.x[2] == pytest.approx(10.0, abs=0.5)
    assert ekf.x[0] > 40.0
    assert abs(ekf.x[1]) < 1.0


def test_heading_decreases_with_positive_gyro(ekf):
    ekf.initialize(heading=0.0)
    for _ in range(50):
        ekf.predict((0.0, 0.0), 0.1, 0.1)
    assert ekf.heading_rad == pytest.approx(-0.5, abs=1e-6)


def test_predict_ignores_bad_dt(ekf):
    ekf.initialize()
    x0 = ekf.x.copy()
    ekf.predict((1.0, 0.0), 0.0, 0.0)
    ekf.predict((1.0, 0.0), 0.0, 5.0)
    np.testing.assert_allclose(ekf.x, x0)


def test_update_gnss_position_pulls(ekf):
    ekf.initialize()
    for _ in range(3):
        ekf.update_gnss_position(5.0, 3.0, accuracy_m=1.0)
    assert ekf.x[0] == pytest.approx(5.0, abs=0.1)
    assert ekf.x[1] == pytest.approx(3.0, abs=0.1)


def test_update_speed_at_rest_uses_heading(ekf):
    ekf.initialize(heading=math.pi / 2)
    ekf.update_speed(5.0, std_mps=0.1)
    assert ekf.speed_mps == pytest.approx(5.0, abs=1.0)
    assert ekf.x[2] > 1.0  # east-ward component


def test_update_speed_moving(ekf):
    ekf.initialize()
    ekf.x[2] = 3.0
    ekf.x[3] = 4.0
    ekf.update_speed(5.0, std_mps=0.05)
    assert ekf.speed_mps == pytest.approx(5.0, abs=0.4)


def test_update_heading_wraps(ekf):
    ekf.initialize(heading=math.pi - 0.1)
    target = -math.pi + 0.2
    ekf.update_heading(target, std_rad=0.05)
    hd = ekf.heading_rad
    assert min(abs(hd - target), abs(hd - target - 2 * math.pi)) < 0.01


def test_update_accel_correction_sets_biases(ekf):
    ekf.initialize()
    ekf.update_accel_correction((0.7, -0.3), std_mps2=0.01)
    assert ekf.x[IDX_ACCEL_BIAS_E] == pytest.approx(0.7, abs=0.02)
    assert ekf.x[IDX_ACCEL_BIAS_N] == pytest.approx(-0.3, abs=0.02)


def test_to_state_maps_components(ekf):
    ekf.initialize(east=1.0, north=2.0, heading=0.5)
    state = ekf.to_state(timestamp=42.0)
    assert state.timestamp == 42.0
    assert state.east_m == pytest.approx(1.0)
    assert state.north_m == pytest.approx(2.0)
    assert state.heading_rad == pytest.approx(0.5)


def test_copy_is_independent(ekf):
    ekf.initialize(1.0, 2.0, 0.1)
    other = ekf.copy()
    ekf.update_gnss_position(5.0, 5.0, 1.0)
    assert other.x[0] == pytest.approx(1.0)


def test_position_std_shrinks_with_fixes(ekf):
    ekf.initialize()
    before = ekf.position_std_m
    for _ in range(10):
        ekf.update_gnss_position(0.0, 0.0, accuracy_m=1.0)
    assert ekf.position_std_m < before