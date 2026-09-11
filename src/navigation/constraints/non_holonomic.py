"""Vehicle-motion (non-holonomic) constraints (D-S9).

A surface vehicle:

    * moves predominantly forward,
    * has small sideways (lateral) velocity,
    * has limited vertical motion,
    * has continuously changing heading, and
    * cannot teleport between road positions.

``apply`` and ``apply_zupt`` are implemented as pseudo-measurements pushed
into the navigation filter (EKF or UKF), which reduces implausible
estimates while keeping the rest of the covariance consistent.
"""

from __future__ import annotations

import math

import numpy as np

from src.navigation.fusion.state_model import STATE_SIZE


class NonHolonomicConstraint:
    """Vehicle-motion constraints applied to a navigation filter."""

    def apply(
        self,
        vehicle,
        heading_rad: float | None = None,
        lateral_std_mps: float = 0.5,
    ) -> None:
        """Constrain the velocity component perpendicular to the heading."""
        if getattr(vehicle, "initialized", False) is False:
            return

        heading = (
            float(heading_rad)
            if heading_rad is not None
            else float(vehicle.x[4])
        )

        # Forward = [sin(h), cos(h)]; perpendicular (right) = [cos(h), -sin(h)].
        H = np.zeros((1, STATE_SIZE))
        H[0, 2] = np.cos(heading)
        H[0, 3] = -np.sin(heading)

        vehicle.update_linear(
            H,
            [0.0],
            np.array([[max(float(lateral_std_mps), 0.05) ** 2]]),
        )

    def apply_zupt(
        self,
        vehicle,
        zero_velocity_std_mps: float = 0.05,
    ) -> None:
        """Zero-velocity update: assume the vehicle is stationary."""
        if getattr(vehicle, "initialized", False) is False:
            return

        H = np.zeros((2, STATE_SIZE))
        H[0, 2] = 1.0
        H[1, 3] = 1.0
        sigma = max(float(zero_velocity_std_mps), 0.01)

        vehicle.update_linear(
            H,
            [0.0, 0.0],
            np.eye(2) * sigma ** 2,
        )

    @staticmethod
    def plausible_position_step_m(
        speed_mps: float,
        dt: float,
        slack_m: float = 5.0,
    ) -> float:
        """Maximum plausible travelled distance in one time step."""
        return float(speed_mps) * max(float(dt), 0.0) + float(slack_m)

    @staticmethod
    def is_teleport(
        prev_east: float,
        prev_north: float,
        new_east: float,
        new_north: float,
        max_jump_m: float,
    ) -> bool:
        """True when a position jump exceeds the plausibility bound."""
        moved = math.hypot(
            float(new_east) - float(prev_east),
            float(new_north) - float(prev_north),
        )
        return moved > max_jump_m