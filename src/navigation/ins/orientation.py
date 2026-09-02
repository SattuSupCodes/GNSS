import math

from navigation.core.math_utils import wrap_angle


class OrientationEstimator:
    """
    Heading estimator for a phone mounted in a fixed orientation
    aligned with the vehicle.

    Important assumption
    --------------------
    The smartphone is mounted in the vehicle such that its forward
    direction is aligned with the vehicle's forward direction.

    Therefore, we do NOT estimate arbitrary phone-to-vehicle orientation.

    The estimator simply integrates yaw rate.

    Heading convention:
        0       = North
        +pi/2   = East
        pi      = South
        -pi/2   = West
    """

    def __init__(self, initial_heading_rad: float = 0.0):
        self.yaw = wrap_angle(initial_heading_rad)
        self.initialized = True

    def reset(self, heading_rad: float = 0.0) -> None:
        """Reset the heading estimate."""
        self.yaw = wrap_angle(heading_rad)

    def update(self, gyro_z: float, dt: float) -> float:
        """
        Propagate heading using gyroscope yaw rate.

        Parameters
        ----------
        gyro_z:
            yaw angular velocity in rad/s.

        dt:
            elapsed time in seconds.

        Returns
        -------
        float:
            updated heading in radians.
        """

        if dt <= 0.0:
            return self.yaw

        self.yaw = wrap_angle(
            self.yaw + gyro_z * dt
        )

        return self.yaw

    def set_heading(self, heading_rad: float) -> None:
        """
        Explicitly set heading.

        Useful when GNSS provides a reliable course or when the
        engine is initialized from a known heading.
        """
        self.yaw = wrap_angle(heading_rad)

    @property
    def heading_rad(self) -> float:
        return self.yaw