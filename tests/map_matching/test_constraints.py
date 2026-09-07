import math

import numpy as np
import pytest

from src.navigation.constraints.non_holonomic import NonHolonomicConstraint
from src.navigation.fusion.ekf import EKF
from src.navigation.fusion.ukf import UKF
from src.navigation.fusion.state_model import IDX_HEADING


@pytest.fixture
def ekf_moving():
    f = EKF()
    f.initialize(heading=0.0)
    f.x[2] = 3.0  # v_east
    f.x[3] = 4.0  # v_north
    return f


@pytest.fixture
def ukf_moving():
    f = UKF()
    f.initialize(heading=0.0)
    f.x[2] = 3.0
    f.x[3] = 4.0
    return f


@pytest.mark.parametrize("filter_factory", [EKF, UKF])
def test_apply_suppresses_lateral_velocity(filter_factory):
    f = filter_factory()
    f.initialize(heading=0.0)  # forward = North
    f.x[2] = 3.0  # east = lateral
    f.x[3] = 4.0
    NonHolonomicConstraint().apply(f, heading_rad=0.0, lateral_std_mps=0.05)
    assert abs(f.x[2]) < 0.2
    assert f.x[3] > 3.0


@pytest.mark.parametrize("filter_factory", [EKF, UKF])
def test_apply_uses_filter_heading_when_omitted(filter_factory):
    f = filter_factory()
    f.initialize(heading=math.pi / 2)  # forward = East
    f.x[2] = 4.0
    f.x[3] = 3.0  # north = lateral
    NonHolonomicConstraint().apply(f, lateral_std_mps=0.05)
    assert abs(f.x[3]) < 0.2
    assert f.x[2] > 3.0


@pytest.mark.parametrize("filter_factory", [EKF, UKF])
def test_apply_zupt_zeroes_velocity(filter_factory):
    f = filter_factory()
    f.initialize()
    f.x[2] = 3.0
    f.x[3] = 4.0
    NonHolonomicConstraint().apply_zupt(f, zero_velocity_std_mps=0.01)
    assert abs(f.x[2]) < 0.1
    assert abs(f.x[3]) < 0.1


def test_apply_wraps_heading_innovation(ekf_moving):
    # A heading barely past +pi is equivalent to -pi + eps.
    ekf_moving.x[IDX_HEADING] = math.pi - 0.01
    NonHolonomicConstraint().apply(ekf_moving, heading_rad=-math.pi + 0.01)
    assert np.isfinite(ekf_moving.x).all()


def test_plausible_position_step():
    nhc = NonHolonomicConstraint()
    assert nhc.plausible_position_step_m(speed_mps=5.0, dt=1.0, slack_m=5.0) == pytest.approx(10.0)


def test_is_teleport():
    nhc = NonHolonomicConstraint()
    assert nhc.is_teleport(0.0, 0.0, 100.0, 0.0, max_jump_m=50.0) is True
    assert nhc.is_teleport(0.0, 0.0, 10.0, 0.0, max_jump_m=50.0) is False


def test_apply_ignores_uninitialized():
    f = EKF()
    NonHolonomicConstraint().apply(f)
    NonHolonomicConstraint().apply_zupt(f)
    assert f.x[2] == 0.0