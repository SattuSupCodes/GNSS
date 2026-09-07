"""Extended Kalman Filter for the 2-D navigation state.

State (see ``fusion/state_model.py``):

    x = [east, north, v_east, v_north, heading, gyro_bias,
         accel_bias_east, accel_bias_north]

Heading is the compass bearing clockwise from North (0 = North, +pi/2 = East).
"""

from __future__ import annotations

import math

import numpy as np

from src.navigation.core.math_utils import wrap_angle
from src.navigation.fusion.state_model import (
    ANGLE_INDICES,
    IDX_HEADING,
    STATE_SIZE,
    default_covariance,
    motion_model,
    process_noise,
    wrap_state_angles,
)
from src.navigation.interfaces.messages import NavigationState


class EKF:
    """A minimal, auditable extended Kalman filter for 2-D dead reckoning."""

    def __init__(self):
        self.x = np.zeros(STATE_SIZE, dtype=float)
        self.P = default_covariance()
        self.initialized = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        self.x = np.zeros(STATE_SIZE, dtype=float)
        self.P = default_covariance()
        self.initialized = False

    def initialize(
        self,
        east: float = 0.0,
        north: float = 0.0,
        heading: float = 0.0,
    ) -> None:
        self.x[:] = 0.0
        self.x[0], self.x[1], self.x[4] = east, north, heading
        wrap_state_angles(self.x)
        self.initialized = True

    def copy(self) -> "EKF":
        other = EKF()
        other.x = self.x.copy()
        other.P = self.P.copy()
        other.initialized = self.initialized
        return other

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #

    def predict(
        self,
        accel_enu,
        gyro_z: float,
        dt: float,
    ) -> None:
        if not self.initialized or dt <= 0.0 or dt > 1.0:
            return

        old = self.x.copy()
        self.x = motion_model(old, accel_enu, gyro_z, dt)
        wrap_state_angles(self.x)

        # Numerical Jacobian keeps the implementation easy to audit/modify.
        F = np.zeros((STATE_SIZE, STATE_SIZE))
        eps = 1e-6
        for i in range(STATE_SIZE):
            xp = old.copy()
            xm = old.copy()
            xp[i] += eps
            xm[i] -= eps
            F[:, i] = (
                motion_model(xp, accel_enu, gyro_z, dt)
                - motion_model(xm, accel_enu, gyro_z, dt)
            ) / (2 * eps)

        self.P = F @ self.P @ F.T + process_noise(dt)
        self.P = 0.5 * (self.P + self.P.T)

    # ------------------------------------------------------------------ #
    # Measurement updates
    # ------------------------------------------------------------------ #

    def _update(
        self,
        z,
        h,
        H,
        R,
        angle_indices=(),
    ):
        z = np.asarray(z, dtype=float)
        h = np.asarray(h, dtype=float)

        innovation = z - h
        for i in angle_indices:
            innovation[i] = wrap_angle(float(innovation[i]))

        S = H @ self.P @ H.T + R
        S = 0.5 * (S + S.T)
        K = self.P @ H.T @ np.linalg.pinv(S)

        self.x = self.x + K @ innovation
        wrap_state_angles(self.x)

        I = np.eye(STATE_SIZE)
        # Joseph form is numerically safer than (I-KH)P.
        self.P = (I - K @ H) @ self.P @ (I - K @ H).T + K @ R @ K.T
        self.P = 0.5 * (self.P + self.P.T)

    def update_linear(
        self,
        H,
        z,
        R,
        angle_indices=(),
    ) -> None:
        """Apply a linear pseudo-measurement ``z = H x + noise``."""
        if not self.initialized:
            return
        H = np.asarray(H, dtype=float)
        self._update(z, H @ self.x, H, R, angle_indices)

    def update_gnss_position(
        self,
        east: float,
        north: float,
        accuracy_m: float,
    ) -> None:
        H = np.zeros((2, STATE_SIZE))
        H[0, 0] = 1.0
        H[1, 1] = 1.0
        sigma = max(float(accuracy_m), 1.0)
        self._update([east, north], [self.x[0], self.x[1]], H, np.eye(2) * sigma ** 2)

    def update_speed(
        self,
        speed_mps: float,
        std_mps: float = 1.0,
    ) -> None:
        speed = max(float(speed_mps), 0.0)
        v = self.x[2:4]
        norm = float(np.linalg.norm(v))
        R = np.array([[max(float(std_mps), 0.1) ** 2]])

        if norm < 1e-4:
            # Speed = ||v|| has zero gradient at rest. Use the current heading
            # as a temporary direction so an AI/GNSS speed measurement can
            # initialize velocity from a standstill.
            H = np.zeros((1, STATE_SIZE))
            H[0, 2] = math.sin(self.x[IDX_HEADING])
            H[0, 3] = math.cos(self.x[IDX_HEADING])
            self._update([speed], [0.0], H, R)
        else:
            H = np.zeros((1, STATE_SIZE))
            H[0, 2] = v[0] / norm
            H[0, 3] = v[1] / norm
            self._update([speed], [norm], H, R)

    def update_heading(
        self,
        heading_rad: float,
        std_rad: float = 0.25,
    ) -> None:
        H = np.zeros((1, STATE_SIZE))
        H[0, IDX_HEADING] = 1.0
        R = np.array([[max(float(std_rad), 0.01) ** 2]])
        self._update([heading_rad], [self.x[IDX_HEADING]], H, R, angle_indices=(0,))

    def update_accel_correction(
        self,
        correction_enu,
        std_mps2: float = 1.0,
    ) -> None:
        """Apply an AI/ML accel-error estimate as a pseudo-measurement on the
        horizontal acceleration biases.
        """
        H = np.zeros((2, STATE_SIZE))
        H[0, 6] = 1.0
        H[1, 7] = 1.0
        z = [correction_enu[0], correction_enu[1]]
        h = [self.x[6], self.x[7]]
        self._update(z, h, H, np.eye(2) * max(float(std_mps2), 0.01) ** 2)

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #

    def to_state(self, timestamp: float = 0.0) -> NavigationState:
        return NavigationState(
            timestamp=float(timestamp),
            east_m=float(self.x[0]),
            north_m=float(self.x[1]),
            velocity_east_mps=float(self.x[2]),
            velocity_north_mps=float(self.x[3]),
            heading_rad=float(self.x[4]),
            gyro_bias_radps=float(self.x[5]),
            accel_bias_east_mps2=float(self.x[6]),
            accel_bias_north_mps2=float(self.x[7]),
        )

    @property
    def position_std_m(self) -> float:
        return float(math.sqrt(max(self.P[0, 0] + self.P[1, 1], 0.0)))

    @property
    def speed_mps(self) -> float:
        return float(math.hypot(self.x[2], self.x[3]))

    @property
    def heading_rad(self) -> float:
        return float(self.x[IDX_HEADING])