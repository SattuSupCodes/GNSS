# src/navigation/core/math_utils.py

from __future__ import annotations

import math
import numpy as np


def wrap_angle(angle_rad: float) -> float:
    return (float(angle_rad) + math.pi) % (2.0 * math.pi) - math.pi


def heading_from_velocity(
    east_mps: float,
    north_mps: float,
    min_speed_mps: float = 0.1,
) -> float | None:
    speed = math.hypot(east_mps, north_mps)

    if speed < min_speed_mps:
        return None

    return wrap_angle(
        math.atan2(
            east_mps,
            north_mps,
        )
    )


def rotation_2d(angle_rad: float) -> np.ndarray:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)

    return np.array(
        [
            [c, -s],
            [s, c],
        ],
        dtype=float,
    )


def velocity_enu_from_heading_speed(
    speed_mps: float,
    heading_rad: float,
) -> tuple[float, float]:
    """(east, north) velocity for a speed and a compass heading (0=North)."""
    return (
        float(speed_mps) * math.sin(float(heading_rad)),
        float(speed_mps) * math.cos(float(heading_rad)),
    )


def heading_difference_rad(
    a_rad: float,
    b_rad: float,
) -> float:
    """Signed, wrapped angular difference ``a - b``."""
    return wrap_angle(float(a_rad) - float(b_rad))


def heading_compass_from_quaternion(
    q: np.ndarray,
    forward_device: tuple[float, float, float] = (0.0, 1.0, 0.0),
) -> float:
    """Compass heading (clockwise from North) of the phone forward axis.

    ``forward_device`` selects the device axis treated as "forward"
    (defaults to device +Y, the phone top edge, matching the alignment
    presets in ``src/calibration/phone_alignment.py``).
    """
    from src.calibration.orientation_estimation import (
        quat_to_rotation_matrix,
    )

    R = np.asarray(quat_to_rotation_matrix(np.asarray(q, dtype=float)))
    forward = R @ np.asarray(forward_device, dtype=float)
    east, north = float(forward[0]), float(forward[1])
    return wrap_angle(math.atan2(east, north))


class LocalENU:
    EARTH_RADIUS_M = 6_378_137.0

    def __init__(
        self,
        latitude_deg: float | None = None,
        longitude_deg: float | None = None,
    ):
        self.initialized = False
        self.lat0_deg = None
        self.lon0_deg = None
        if latitude_deg is not None or longitude_deg is not None:
            self.set_origin(latitude_deg, longitude_deg)

    def reset(self) -> None:
        self.initialized = False
        self.lat0_deg = None
        self.lon0_deg = None

    def set_origin(
        self,
        latitude_deg: float,
        longitude_deg: float,
    ) -> None:
        self.lat0_deg = float(latitude_deg)
        self.lon0_deg = float(longitude_deg)
        self.initialized = True

    def to_local(
        self,
        latitude_deg: float,
        longitude_deg: float,
    ) -> tuple[float, float]:

        if not self.initialized:
            self.set_origin(latitude_deg, longitude_deg)

        lat = math.radians(float(latitude_deg))
        lat0 = math.radians(self.lat0_deg)

        dlat = math.radians(
            float(latitude_deg) - self.lat0_deg
        )
        dlon = math.radians(
            float(longitude_deg) - self.lon0_deg
        )

        north = dlat * self.EARTH_RADIUS_M
        east = (
            dlon
            * self.EARTH_RADIUS_M
            * math.cos(lat0)
        )

        return float(east), float(north)

    def to_xy(
        self,
        latitude_deg: float,
        longitude_deg: float,
    ) -> tuple[float, float]:
        """Alias for :meth:`to_local` using the ``to_xy`` naming."""
        return self.to_local(latitude_deg, longitude_deg)

    def to_geodetic(
        self,
        east_m: float,
        north_m: float,
    ) -> tuple[float, float]:

        if not self.initialized:
            raise RuntimeError("ENU origin is not initialized")

        lat0 = math.radians(self.lat0_deg)

        latitude_deg = (
            self.lat0_deg
            + math.degrees(
                float(north_m) / self.EARTH_RADIUS_M
            )
        )

        longitude_deg = (
            self.lon0_deg
            + math.degrees(
                float(east_m)
                / (
                    self.EARTH_RADIUS_M
                    * math.cos(lat0)
                )
            )
        )

        return float(latitude_deg), float(longitude_deg)

    def to_ll(
        self,
        east_m: float,
        north_m: float,
    ) -> tuple[float, float]:
        """Alias for :meth:`to_geodetic` using the ``to_ll`` naming."""
        return self.to_geodetic(east_m, north_m)