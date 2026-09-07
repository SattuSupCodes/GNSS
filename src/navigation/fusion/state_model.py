"""Shared state definitions and motion model for the 2-D navigation filters.

The EKF and UKF both propagate the same 8-dimensional state:

    x = [east, north, v_east, v_north, heading, gyro_bias,
         accel_bias_east, accel_bias_north]

Conventions (standardised across the navigation backend):

    * World frame is ENU: +x East, +y North, +z Up.
    * ``heading`` is the compass bearing (clockwise from North):
        0 = North, +pi/2 = East.
    * A positive ``gyro_z`` is counter-clockwise about the up axis
      (a left turn), so compass heading *decreases* with positive gyro_z.
"""

from __future__ import annotations

import numpy as np

from src.navigation.core.math_utils import wrap_angle

STATE_SIZE = 8

IDX_E = 0
IDX_N = 1
IDX_VE = 2
IDX_VN = 3
IDX_HEADING = 4
IDX_GYRO_BIAS = 5
IDX_ACCEL_BIAS_E = 6
IDX_ACCEL_BIAS_N = 7

ANGLE_INDICES: tuple[int, ...] = (IDX_HEADING,)

#: Names for each state component (used for tuning/debugging only).
STATE_NAMES = (
    "east_m",
    "north_m",
    "velocity_east_mps",
    "velocity_north_mps",
    "heading_rad",
    "gyro_bias_radps",
    "accel_bias_east_mps2",
    "accel_bias_north_mps2",
)


def wrap_state_angles(x: np.ndarray) -> np.ndarray:
    """Wrap all periodic state components (heading) into ``[-pi, pi)``.

    Handles both a single state vector and a stacked (N, STATE_SIZE) array
    of sigma points.
    """
    if x.ndim > 1:
        x[:, IDX_HEADING] = (x[:, IDX_HEADING] + np.pi) % (2.0 * np.pi) - np.pi
    else:
        x[IDX_HEADING] = wrap_angle(x[IDX_HEADING])
    return x


def motion_model(
    x: np.ndarray,
    accel_enu: tuple[float, float] | np.ndarray,
    gyro_z: float,
    dt: float,
) -> np.ndarray:
    """Discrete-time constant-acceleration motion model.

    Bias-corrected acceleration/gyro are integrated; heading follows the
    compass convention (heading_new = heading - (gyro_z - bias) * dt).
    """
    y = np.array(x, dtype=float)

    ae, an = float(accel_enu[0]), float(accel_enu[1])

    ae_corrected = ae - y[IDX_ACCEL_BIAS_E]
    an_corrected = an - y[IDX_ACCEL_BIAS_N]
    omega = gyro_z - y[IDX_GYRO_BIAS]

    y[IDX_E] = y[IDX_E] + y[IDX_VE] * dt + 0.5 * ae_corrected * dt * dt
    y[IDX_N] = y[IDX_N] + y[IDX_VN] * dt + 0.5 * an_corrected * dt * dt
    y[IDX_VE] = y[IDX_VE] + ae_corrected * dt
    y[IDX_VN] = y[IDX_VN] + an_corrected * dt
    y[IDX_HEADING] = wrap_angle(y[IDX_HEADING] - omega * dt)

    return y


def process_noise(dt: float) -> np.ndarray:
    """Discrete process noise covariance for a time step ``dt``."""
    factor = max(float(dt), 1e-3)
    q = np.diag(
        [
            0.01 ** 2,     # position east
            0.01 ** 2,     # position north
            0.25 ** 2,     # velocity east
            0.25 ** 2,     # velocity north
            0.02 ** 2,     # heading
            0.0005 ** 2,   # gyro bias
            0.01 ** 2,     # accel bias east
            0.01 ** 2,     # accel bias north
        ]
    )
    return q * factor


def default_covariance() -> np.ndarray:
    """Reasonable initial covariance for a local-frame start."""
    return np.diag(
        [
            25.0,          # position east
            25.0,          # position north
            4.0,           # velocity east
            4.0,           # velocity north
            0.25,          # heading
            0.03 ** 2,     # gyro bias
            0.5 ** 2,      # accel bias east
            0.5 ** 2,      # accel bias north
        ]
    )