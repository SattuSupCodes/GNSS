import math

import numpy as np

from src.navigation.interfaces.messages import NavigationState
from src.navigation.core.math_utils import wrap_angle

class InertialNavigator:
    """
    Classical 2-D inertial navigation / dead reckoning.

    Coordinate frame:
        East  -> x
        North -> y

    Input acceleration must already be:

        1. calibrated
        2. gravity compensated
        3. transformed from phone frame to ENU

    This class intentionally contains:
        - NO GNSS correction
        - NO AI correction
        - NO map matching

    It establishes the naive inertial/dead-reckoning baseline.
    """

    def __init__(
      self,
        max_dt=1.0,
        stationary_speed_threshold=0.05,
    ):
        self.max_dt = float(max_dt)
        self.stationary_speed_threshold = float(stationary_speed_threshold)
    def propagate(self, state, acceleration_enu, heading_rad, gyro_z, dt):
        if dt <= 0.0 or dt > self.max_dt:
            return state

        ae, an = map(float, acceleration_enu)

        ae_corrected = ae - state.accel_bias_east_mps2
        an_corrected = an - state.accel_bias_north_mps2

        acceleration = np.array(
            [ae_corrected, an_corrected],
            dtype=float,
        )

        velocity = np.array(
            [
                state.velocity_east_mps,
                state.velocity_north_mps,
            ],
            dtype=float,
        )

        # Basic inertial integration.
        position_delta = (
            velocity * dt
            + 0.5 * acceleration * dt**2
        )

        state.east_m += float(position_delta[0])
        state.north_m += float(position_delta[1])

        velocity_new = velocity + acceleration * dt

        state.velocity_east_mps = float(velocity_new[0])
        state.velocity_north_mps = float(velocity_new[1])

        state.heading_rad = wrap_angle(heading_rad)
        state.timestamp += dt

        # --------------------------------------------------------------
        # Stationary zero-velocity correction
        # --------------------------------------------------------------
        #
        # If the estimated horizontal velocity is extremely small,
        # treat the vehicle as stationary and explicitly remove the
        # accumulated numerical velocity.
        #
        # This prevents tiny IMU errors during stops from accumulating
        # into artificial motion.
        speed = float(np.linalg.norm(velocity_new))

        if speed < self.stationary_speed_threshold:
            state.velocity_east_mps = 0.0
            state.velocity_north_mps = 0.0

        return state