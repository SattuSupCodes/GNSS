import numpy as np

from navigation.core.math_utils import wrap_angle
from navigation.interfaces.messages import NavigationState


class InertialNavigator:
    """
    Classical 2-D inertial navigation / dead reckoning.

    The navigator operates in a local ENU frame:

        East  -> x
        North -> y

    The input acceleration must already be:

        1. calibrated
        2. transformed from phone frame to navigation frame
        3. gravity compensated

    Aaqib's preprocessing pipeline is expected to eventually provide this.

    This class intentionally contains NO AI and NO GNSS correction.

    Its purpose is to establish the naive INS baseline.
    """

    def __init__(
        self,
        max_dt: float = 1.0,
        stationary_speed_threshold: float = 0.05,
    ):
        self.max_dt = max_dt
        self.stationary_speed_threshold = stationary_speed_threshold

    def propagate(
        self,
        state: NavigationState,
        acceleration_enu,
        heading_rad: float,
        gyro_z: float,
        dt: float,
    ) -> NavigationState:
        """
        Propagate the navigation state forward using IMU acceleration.

        Parameters
        ----------
        state:
            Current navigation state.

        acceleration_enu:
            (east_acceleration, north_acceleration) in m/s^2.

        heading_rad:
            Current heading in radians.

        gyro_z:
            Gyroscope yaw rate in rad/s.

        dt:
            Time step in seconds.

        Returns
        -------
        NavigationState
            Updated state.
        """

        # Reject invalid time intervals.
        if dt <= 0.0 or dt > self.max_dt:
            return state

        ae, an = map(float, acceleration_enu)

        # ---------------------------------------------------------
        # 1. Correct acceleration using estimated accelerometer bias
        # ---------------------------------------------------------

        ae_corrected = (
            ae - state.accel_bias_east_mps2
        )

        an_corrected = (
            an - state.accel_bias_north_mps2
        )

        acceleration = np.array(
            [ae_corrected, an_corrected],
            dtype=float,
        )

        # ---------------------------------------------------------
        # 2. Current velocity
        # ---------------------------------------------------------

        velocity = np.array(
            [
                state.velocity_east_mps,
                state.velocity_north_mps,
            ],
            dtype=float,
        )

        # ---------------------------------------------------------
        # 3. Position propagation
        #
        # p(k+1) =
        # p(k) + v(k)*dt + 1/2*a*dt^2
        # ---------------------------------------------------------

        position_delta = (
            velocity * dt
            + 0.5 * acceleration * dt * dt
        )

        state.east_m += float(position_delta[0])
        state.north_m += float(position_delta[1])

        # ---------------------------------------------------------
        # 4. Velocity propagation
        #
        # v(k+1) = v(k) + a*dt
        # ---------------------------------------------------------

        velocity_new = (
            velocity + acceleration * dt
        )

        state.velocity_east_mps = float(
            velocity_new[0]
        )

        state.velocity_north_mps = float(
            velocity_new[1]
        )

        # ---------------------------------------------------------
        # 5. Heading
        #
        # For the naive INS baseline, heading is supplied by the
        # orientation estimator.
        # ---------------------------------------------------------

        state.heading_rad = wrap_angle(
            heading_rad
        )

        # ---------------------------------------------------------
        # 6. Timestamp
        # ---------------------------------------------------------

        state.timestamp += dt

        return state