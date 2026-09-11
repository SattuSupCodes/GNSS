"""Unscented Kalman Filter for the 2-D navigation state.

Uses the same state vector, motion model and conventions as the EKF (see
``fusion/state_model.py`` and ``fusion/ekf.py``), but propagates the state
distribution through sigma points. This avoids the linearisation of the
motion model and of the nonlinear speed measurement ``||v||`` used by the
EKF, at a modest cost in compute.

Heading is a periodic component: it is wrapped before inclusion in the
weighted mean / covariance, and innovations are wrapped before the update.
"""

from __future__ import annotations

import math

import numpy as np

from src.navigation.core.math_utils import wrap_angle
from src.navigation.fusion.state_model import (
    IDX_HEADING,
    STATE_SIZE,
    default_covariance,
    motion_model,
    process_noise,
    wrap_state_angles,
)
from src.navigation.interfaces.messages import NavigationState


def _symmetrize(P: np.ndarray) -> np.ndarray:
    return 0.5 * (P + P.T)


def _wrapped_covariance(
    points: np.ndarray,
    mean: np.ndarray,
    weights_c: np.ndarray,
) -> np.ndarray:
    """Weighted covariance with per-row angle wrapping relative to mean."""
    deviations = points - mean
    deviations[:, IDX_HEADING] = np.array(
        [wrap_angle(float(x)) for x in deviations[:, IDX_HEADING]]
    )
    P = (deviations.T * weights_c) @ deviations
    return _symmetrize(P)


class UKF:
    """Scaled unscented Kalman filter over the 8-state navigation model."""

    def __init__(
        self,
        alpha: float = 1.0,
        beta: float = 2.0,
        kappa: float = 0.0,
    ):
        n = STATE_SIZE
        lam = float(alpha) ** 2 * (n + kappa) - n
        self._lambda = lam
        self._c = n + lam

        self._weights_m = np.zeros(2 * n + 1)
        self._weights_c = np.zeros(2 * n + 1)
        self._weights_m[0] = lam / self._c
        self._weights_c[0] = lam / self._c + (1.0 - float(alpha) ** 2 + beta)
        for i in range(1, 2 * n + 1):
            self._weights_m[i] = 0.5 / self._c
            self._weights_c[i] = 0.5 / self._c

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

    def copy(self) -> "UKF":
        other = UKF()
        other._weights_m = self._weights_m.copy()
        other._weights_c = self._weights_c.copy()
        other._lambda = self._lambda
        other._c = self._c
        other.x = self.x.copy()
        other.P = self.P.copy()
        other.initialized = self.initialized
        return other

    # ------------------------------------------------------------------ #
    # Sigma points
    # ------------------------------------------------------------------ #

    def _sigma_points(self, x: np.ndarray, P: np.ndarray) -> np.ndarray:
        n = STATE_SIZE
        P = _symmetrize(P)
        try:
            A = np.linalg.cholesky(P)
        except np.linalg.LinAlgError:
            A = np.linalg.cholesky(P + np.eye(n) * 1e-9)

        pts = np.tile(x, (2 * n + 1, 1))
        scale = math.sqrt(self._c)
        for i in range(n):
            pts[i + 1] = x + scale * A[:, i]
            pts[n + 1 + i] = x - scale * A[:, i]
        wrap_state_angles(pts)
        return pts

    def _sigma_mean(self, pts: np.ndarray) -> np.ndarray:
        # Heading: circular weighted mean; others: ordinary weighted mean.
        mean = self._weights_m @ pts
        sin_h = np.sum(self._weights_m * np.sin(pts[:, IDX_HEADING]))
        cos_h = np.sum(self._weights_m * np.cos(pts[:, IDX_HEADING]))
        mean[IDX_HEADING] = wrap_angle(math.atan2(sin_h, cos_h))
        return mean

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

        pts = self._sigma_points(self.x, self.P)
        transformed = np.array(
            [motion_model(p, accel_enu, gyro_z, dt) for p in pts],
            dtype=float,
        )
        mean = self._sigma_mean(transformed)
        cov = _wrapped_covariance(transformed, mean, self._weights_c)
        cov = cov + process_noise(dt)

        self.x = mean
        self.P = _symmetrize(cov)

    # ------------------------------------------------------------------ #
    # Measurement updates
    # ------------------------------------------------------------------ #

    def _measurement_update(
        self,
        z,
        h_func,
        R,
        angle_indices=(),
    ):
        if not self.initialized:
            return

        z = np.asarray(z, dtype=float).reshape(-1)
        m = len(z)
        R = np.asarray(R, dtype=float)

        pts = self._sigma_points(self.x, self.P)
        zpts = np.array([np.asarray(h_func(p), dtype=float).reshape(-1) for p in pts])

        zmean = self._weights_m @ zpts
        for i in angle_indices:
            if i < m:
                s = np.sum(self._weights_m * np.sin(zpts[:, i]))
                c = np.sum(self._weights_m * np.cos(zpts[:, i]))
                zmean[i] = wrap_angle(math.atan2(s, c))

        zdev = zpts - zmean
        for i in angle_indices:
            if i < m:
                zdev[:, i] = np.array(
                    [wrap_angle(float(x)) for x in zdev[:, i]]
                )

        S = (zdev.T * self._weights_c) @ zdev + R
        S = _symmetrize(S)

        xdev = pts - self.x
        xdev[:, IDX_HEADING] = np.array(
            [wrap_angle(float(x)) for x in xdev[:, IDX_HEADING]]
        )

        Pxz = (xdev.T * self._weights_c) @ zdev
        K = Pxz @ np.linalg.pinv(S)

        innovation = np.asarray(z, dtype=float) - zmean
        for i in angle_indices:
            if i < m:
                innovation[i] = wrap_angle(float(innovation[i]))

        self.x = self.x + K @ innovation
        wrap_state_angles(self.x)
        self.P = _symmetrize(self.P - K @ S @ K.T)

    def update_linear(
        self,
        H,
        z,
        R,
        angle_indices=(),
    ) -> None:
        H = np.asarray(H, dtype=float)

        def h_func(x):
            return H @ np.asarray(x, dtype=float)

        self._measurement_update(z, h_func, R, angle_indices)

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
        self.update_linear(H, [east, north], np.eye(2) * sigma ** 2)

    def update_speed(
        self,
        speed_mps: float,
        std_mps: float = 1.0,
    ) -> None:
        sigma = max(float(std_mps), 0.1)

        def h_func(x):
            return [float(np.linalg.norm(x[2:4]))]

        self._measurement_update(
            [max(float(speed_mps), 0.0)],
            h_func,
            np.array([[sigma ** 2]]),
        )

    def update_heading(
        self,
        heading_rad: float,
        std_rad: float = 0.25,
    ) -> None:
        H = np.zeros((1, STATE_SIZE))
        H[0, IDX_HEADING] = 1.0
        sigma = max(float(std_rad), 0.01)
        self.update_linear(H, [heading_rad], np.array([[sigma ** 2]]), angle_indices=(0,))

    def update_accel_correction(
        self,
        correction_enu,
        std_mps2: float = 1.0,
    ) -> None:
        H = np.zeros((2, STATE_SIZE))
        H[0, 6] = 1.0
        H[1, 7] = 1.0
        sigma = max(float(std_mps2), 0.01)
        self.update_linear(
            H,
            [correction_enu[0], correction_enu[1]],
            np.eye(2) * sigma ** 2,
        )

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