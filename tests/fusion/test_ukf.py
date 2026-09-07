import math

import numpy as np
import pytest

from src.navigation.fusion.ukf import UKF


@pytest.fixture
def ukf():
    return UKF()


def compare_ekf_and_ukf(ekf_result, ukf_result, rtol=0.05):
    np.testing.assert_allclose(ekf_result, ukf_result, rtol=rtol)


def test_initialize_sets_state(ukf):
    ukf.initialize(east=1.0, north=2.0, heading=math.pi / 2)
    assert ukf.x[0] == pytest.approx(1.0)
    assert ukf.x[1] == pytest.approx(2.0)
    assert ukf.heading_rad == pytest.approx(math.pi / 2)


def test_predict_constant_accel_east(ukf):
    ukf.initialize(0.0, 0.0, heading=math.pi / 2)
    for _ in range(100):
        ukf.predict((1.0, 0.0), 0.0, 0.1)
    assert ukf.x[2] == pytest.approx(10.0, abs=0.5)
    assert ukf.x[0] > 40.0
    assert abs(ukf.x[1]) < 1.0


def test_heading_decreases_with_positive_gyro(ukf):
    ukf.initialize(heading=0.0)
    for _ in range(50):
        ukf.predict((0.0, 0.0), 0.1, 0.1)
    assert ukf.heading_rad == pytest.approx(-0.5, abs=1e-3)


def test_update_gnss_position_pulls(ukf):
    ukf.initialize()
    for _ in range(3):
        ukf.update_gnss_position(5.0, 3.0, accuracy_m=1.0)
    assert ukf.x[0] == pytest.approx(5.0, abs=0.2)
    assert ukf.x[1] == pytest.approx(3.0, abs=0.2)


def test_update_speed_nonlinear_norm(ukf):
    ukf.initialize()
    ukf.x[2] = 3.0
    ukf.x[3] = 4.0
    ukf.update_speed(5.0, std_mps=0.05)
    assert ukf.speed_mps == pytest.approx(5.0, abs=1.0)


def test_update_heading_wraps(ukf):
    ukf.initialize(heading=math.pi - 0.1)
    target = -math.pi + 0.2
    ukf.update_heading(target, std_rad=0.05)
    hd = ukf.heading_rad
    assert min(abs(hd - target), abs(hd - target - 2 * math.pi)) < 0.01


def test_update_accel_correction_sets_biases(ukf):
    ukf.initialize()
    ukf.update_accel_correction((0.7, -0.3), std_mps2=0.01)
    assert ukf.x[6] == pytest.approx(0.7, abs=0.05)
    assert ukf.x[7] == pytest.approx(-0.3, abs=0.05)


def test_ukf_matches_ekf_on_linear_scenario():
    from src.navigation.fusion.ekf import EKF

    def run(factory):
        f = factory()
        f.initialize(0.0, 0.0, heading=math.pi / 4)
        for _ in range(20):
            f.predict((0.3, 0.1), 0.01, 0.1)
            f.update_gnss_position(0.0, 0.0, accuracy_m=10.0)
        return f.x

    ekf_v = run(EKF)
    ukf_v = run(UKF)
    np.testing.assert_allclose(ekf_v, ukf_v, rtol=0.05, atol=1e-30)


def test_to_state_maps_components(ukf):
    ukf.initialize(east=1.0, north=2.0, heading=0.5)
    state = ukf.to_state(timestamp=42.0)
    assert state.east_m == pytest.approx(1.0)
    assert state.north_m == pytest.approx(2.0)
    assert state.heading_rad == pytest.approx(0.5)


def test_copy_is_independent(ukf):
    ukf.initialize(1.0, 2.0, 0.1)
    other = ukf.copy()
    ukf.update_gnss_position(5.0, 5.0, 1.0)
    assert other.x[0] == pytest.approx(1.0)