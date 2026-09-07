# src/navigation/ins/orientation.py

from __future__ import annotations

from src.navigation.core.math_utils import wrap_angle


class OrientationEstimator:
    """
    Heading estimator for a phone mounted straight in the vehicle.

    Heading convention:
        0       = North
        +pi/2   = East
        pi      = South
        -pi/2   = West

    Assumption:
        phone +X = vehicle forward
        phone +Y = vehicle left
        phone +Z = upward

    With the standard right-handed ENU convention, positive gyro-Z
    corresponds to counter-clockwise heading change in this convention.
    """

    def __init__(self, initial_heading_rad: float = 0.0):
        self._heading_rad = wrap_angle(initial_heading_rad)

    def reset(self, heading_rad: float = 0.0) -> None:
        self._heading_rad = wrap_angle(heading_rad)

    def update(self, gyro_z: float, dt: float) -> float:
        if dt <= 0.0:
            return self._heading_rad

        # Right-hand +Z rotation is opposite to clockwise compass heading.
        self._heading_rad = wrap_angle(
            self._heading_rad - float(gyro_z) * float(dt)
        )

        return self._heading_rad

    def set_heading(self, heading_rad: float) -> None:
        self._heading_rad = wrap_angle(heading_rad)

    @property
    def heading_rad(self) -> float:
        return self._heading_rad