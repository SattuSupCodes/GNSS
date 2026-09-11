import math

import pytest

from src.navigation.interfaces.messages import NavigationState
from src.navigation.ins.ins import InertialNavigator


def make_state():
    return NavigationState(
        timestamp=0.0,
        east_m=0.0,
        north_m=0.0,
        velocity_east_mps=0.0,
        velocity_north_mps=0.0,
        heading_rad=0.0,
        gyro_bias_radps=0.0,
        accel_bias_east_mps2=0.0,
        accel_bias_north_mps2=0.0,
    )


def test_propagate_accumulates_position():
    nav = InertialNavigator()
    state = make_state()
    for _ in range(10):
        state = nav.propagate(state, (0.0, 1.0), 0.0, 0.0, 0.1)
    assert state.north_m > 0.3
    assert state.velocity_north_mps == pytest.approx(1.0, abs=1e-6)
    assert state.east_m == pytest.approx(0.0, abs=1e-9)


def test_propagate_stores_heading_and_wraps():
    nav = InertialNavigator()
    state = make_state()
    state = nav.propagate(state, (0.0, 0.0), math.pi + 0.1, 0.0, 0.1)
    assert state.heading_rad == pytest.approx(-math.pi + 0.1, abs=1e-9)


def test_propagate_applies_bias_correction():
    nav = InertialNavigator()
    state = make_state()
    state.accel_bias_north_mps2 = 0.5
    state = nav.propagate(state, (0.0, 1.0), 0.0, 0.0, 0.1)
    assert state.velocity_north_mps == pytest.approx(0.05, abs=1e-9)


def test_stationary_zero_velocity_correction():
    nav = InertialNavigator()
    nav.stationary_speed_threshold = 0.1
    state = make_state()
    state.velocity_north_mps = 0.05
    state = nav.propagate(state, (0.0, 0.0), 0.0, 0.0, 0.1)
    assert state.velocity_north_mps == 0.0


def test_propagate_ignores_excessive_dt():
    nav = InertialNavigator(max_dt=1.0)
    state = make_state()
    out = nav.propagate(state, (0.0, 1.0), 0.0, 0.0, 5.0)
    assert out is state
    assert state.north_m == 0.0