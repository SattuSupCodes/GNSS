"""Smartphone orientation / attitude estimation foundation.

Estimates the orientation of the phone relative to a navigation (world) frame
using accelerometer, gyroscope and magnetometer. This is a *practical*,
configurable estimator — not a research-grade INS attitude filter.

Conventions (all explicit, documented, and self-consistent):

* Frame: device frame (Android accelerometer convention: X = right, Y = up the
  long edge / screen top, Z = out of the screen) -> world ENU frame.
* Quaternions are scalar-first ``(w, x, y, z)``, unit norm.
* ``quat_rotate(q, v)`` rotates a *device* vector into the *world* frame.
* Euler angles (yaw, pitch, roll) follow ``R = Rz(yaw) * Ry(pitch) * Rx(roll)``
  applied device -> world. ``yaw`` is the rotation about world up; it is a
  *rotation angle*, not by itself the bearing of the phone's top edge (that
  mapping depends on the mount convention handled in
  :mod:`src.calibration.phone_alignment`).
* GNSS course-over-ground is NOT treated as phone yaw (see docs/calibration.md).

What is estimated vs measured vs unavailable
--------------------------------------------
Roll/pitch: estimated from the (low-frequency) gravity vector carried by the
accelerometer. Yaw: estimated from the tilt-compensated magnetometer where the
field magnitude looks like Earth's field, and integrated from the gyroscope
otherwise (drifting). The per-sample ``heading_source`` and ``heading_quality``
columns say which of these held for each sample instead of pretending every
heading is trustworthy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..data.data_schema import (
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    MAG_X,
    MAG_Y,
    MAG_Z,
    TS_SEC,
)

QUATERNION_COLUMNS = ("orient_qw", "orient_qx", "orient_qy", "orient_qz")
EULER_COLUMNS = ("orient_roll_deg", "orient_pitch_deg", "orient_yaw_deg")
STATUS_COLUMNS = (
    "orient_heading_source",
    "orient_heading_quality",
    "orient_tilt_quality",
)
ORIENTATION_COLUMNS = QUATERNION_COLUMNS + EULER_COLUMNS + STATUS_COLUMNS

# Earth's magnetic field magnitude bounds (microtesla) used to decide whether a
# magnetometer sample is usable for heading.
MAG_FIELD_MIN_UT = 20.0
MAG_FIELD_MAX_UT = 70.0


# --------------------------------------------------------------------------- #
# Quaternion toolkit (scalar-first).                                           #
# --------------------------------------------------------------------------- #


def quat_normalize(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    n = np.linalg.norm(q)
    if n < 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return q / n


def quat_multiply(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Hamilton product p (x) q: applies q first, then p."""
    pw, px, py, pz = p
    qw, qx, qy, qz = q
    return np.array(
        [
            pw * qw - px * qx - py * qy - pz * qz,
            pw * qx + px * qw + py * qz - pz * qy,
            pw * qy - px * qz + py * qw + pz * qx,
            pw * qz + px * qy - py * qx + pz * qw,
        ]
    )


def quat_conjugate(q: np.ndarray) -> np.ndarray:
    q = np.asarray(q, dtype=float)
    return q * np.array([1.0, -1.0, -1.0, -1.0])


def quat_rotate(q: np.ndarray, v: np.ndarray, inverse: bool = False) -> np.ndarray:
    """Rotate vector ``v`` (device frame) into world frame by unit quaternion ``q``.

    Rotations are proper: ``Rotation(q).apply``. With ``inverse=True`` the
    conjugate rotation (world -> device) is applied.
    """
    q = quat_normalize(q)
    qv = np.concatenate([[0.0], np.asarray(v, dtype=float)])
    if inverse:
        qv = quat_multiply(quat_conjugate(q), qv)
        qvi = quat_multiply(qv, q)
    else:
        qv = quat_multiply(q, qv)
        qvi = quat_multiply(qv, quat_conjugate(q))
    return qvi[1:]


def quat_from_axis_angle(axis: np.ndarray, angle_rad: float) -> np.ndarray:
    axis = np.asarray(axis, dtype=float)
    n = np.linalg.norm(axis)
    if n < 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    axis = axis / n
    return np.array(
        [
            math.cos(angle_rad / 2.0),
            *(axis * math.sin(angle_rad / 2.0)),
        ]
    )


def quat_from_rotation_matrix(R: np.ndarray) -> np.ndarray:
    """Robust quaternion from a 3x3 rotation matrix (Shepperd's method)."""
    R = np.asarray(R, dtype=float)
    tr = np.trace(R)
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2.0
        q = np.array(
            [
                0.25 * s,
                (R[2, 1] - R[1, 2]) / s,
                (R[0, 2] - R[2, 0]) / s,
                (R[1, 0] - R[0, 1]) / s,
            ]
        )
    else:
        i = int(np.argmax(np.diag(R)))
        J = np.roll(np.arange(3), -i)
        t = math.sqrt(1.0 + R[i, i] - R[J[1], J[1]] - R[J[2], J[2]])
        s = 2.0 * t
        out = np.zeros(4)
        out[0] = (R[J[2], J[1]] - R[J[1], J[2]]) / s
        out[i + 1] = 0.25 * s
        out[J[1] + 1] = (R[J[1], i] + R[i, J[1]]) / s
        out[J[2] + 1] = (R[J[2], i] + R[i, J[2]]) / s
        q = out
    return quat_normalize(q)


def quat_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    q = quat_normalize(q)
    w, x, y, z = q
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def quat_from_euler(yaw_rad: float, pitch_rad: float, roll_rad: float) -> np.ndarray:
    """Quaternion for ``R = Rz(yaw) * Ry(pitch) * Rx(roll)`` (device -> world)."""
    qz = quat_from_axis_angle([0.0, 0.0, 1.0], yaw_rad)
    qy = quat_from_axis_angle([0.0, 1.0, 0.0], pitch_rad)
    qx = quat_from_axis_angle([1.0, 0.0, 0.0], roll_rad)
    return quat_normalize(quat_multiply(qz, quat_multiply(qy, qx)))


def quat_to_euler(q: np.ndarray) -> Tuple[float, float, float]:
    """(yaw, pitch, roll) in radians for ``R = Rz(yaw)*Ry(pitch)*Rx(roll)``."""
    R = quat_to_rotation_matrix(q)
    sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    if sy > 1e-9:
        yaw = math.atan2(R[1, 0], R[0, 0])
        pitch = math.atan2(-R[2, 0], sy)
        roll = math.atan2(R[2, 1], R[2, 2])
    else:
        yaw = 0.0
        pitch = math.atan2(-R[2, 0], sy)
        roll = math.atan2(-R[1, 2], R[1, 1])
    return yaw, pitch, roll


def quat_from_two_vectors(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Unit quaternion rotating ``a`` onto ``b`` (both non-zero vectors)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    cos_ang = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if cos_ang > 0.99999:
        return np.array([1.0, 0.0, 0.0, 0.0])
    if cos_ang < -0.99999:
        axis = np.cross(a, [1.0, 0.0, 0.0])
        if np.linalg.norm(axis) < 1e-8:
            axis = np.cross(a, [0.0, 1.0, 0.0])
        return quat_from_axis_angle(axis, math.pi)
    axis = np.cross(a, b)
    return quat_from_axis_angle(axis, math.acos(cos_ang))


def slerp(q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
    """Spherical linear interpolation between two unit quaternions."""
    q0, q1 = quat_normalize(q0), quat_normalize(q1)
    d = float(np.clip(np.dot(q0, q1), -1.0, 1.0))
    sign = 1.0 if d >= 0.0 else -1.0
    q1 = q1 * sign
    d = abs(d)
    if d > 0.9995:
        return quat_normalize(q0 + t * (q1 - q0))
    omega = math.acos(d)
    so = math.sin(omega)
    return (q0 * math.sin((1.0 - t) * omega) + q1 * math.sin(t * omega)) / so


def is_rotation_matrix(R: np.ndarray, tol: float = 1e-6) -> bool:
    """True when ``R`` is a valid 3x3 rotation (orthogonal, det=+1)."""
    R = np.asarray(R, dtype=float)
    if R.shape != (3, 3):
        return False
    check = R @ R.T - np.eye(3)
    return bool(np.max(np.abs(check)) < tol) and abs(float(np.linalg.det(R)) - 1.0) < tol


# --------------------------------------------------------------------------- #
# Tilt and heading primitives                                                  #
# --------------------------------------------------------------------------- #


def roll_pitch_from_gravity(
    gx: np.ndarray, gy: np.ndarray, gz: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Estimate roll and pitch (radians) from the gravity vector (device frame).

    With the phone flat (screen up, sensor Z opposite gravity) roll/pitch are 0.
    ``gx, gy, gz`` should be the low-frequency gravity component of the
    accelerometer (e.g. from :mod:`src.calibration.gravity_estimation`).
    """
    gx, gy, gz = map(lambda a: np.asarray(a, dtype=float), (gx, gy, gz))
    norm = np.sqrt(gx**2 + gy**2 + gz**2)
    with np.errstate(divide="ignore", invalid="ignore"):
        roll = np.arctan2(gy, gz)
        pitch = np.arctan2(-gx, np.sqrt(gy**2 + gz**2))
    roll[~np.isfinite(roll)] = np.nan
    pitch[~np.isfinite(pitch)] = np.nan
    return roll, pitch


def tilt_compensated_magnetometer(
    mx: np.ndarray,
    my: np.ndarray,
    mz: np.ndarray,
    roll: np.ndarray,
    pitch: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rotate the magnetometer reading into the horizontal (world-xy) plane.

    Returns the (x, y, z) components in a yaw-free world frame (z ~ 0 when the
    compensation is exact). Rows with any non-finite input are NaN.
    """
    mx, my, mz = map(lambda a: np.asarray(a, dtype=float), (mx, my, mz))
    roll = np.asarray(roll, dtype=float)
    pitch = np.asarray(pitch, dtype=float)
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    hx = mx * cp + my * sp * sr + mz * sp * cr
    hy = my * cr - mz * sr
    hz = -mx * sp + my * cp * sr + mz * cp * cr
    valid = (
        np.isfinite(mx)
        & np.isfinite(my)
        & np.isfinite(mz)
        & np.isfinite(roll)
        & np.isfinite(pitch)
    )
    return np.where(valid, hx, np.nan), np.where(valid, hy, np.nan), np.where(valid, hz, np.nan)


def magnetometer_heading_from_horizontal(hx: np.ndarray, hy: np.ndarray) -> np.ndarray:
    """Yaw (radians, device->world rotation about up) from a horizontal mag field.

    Derivation: with v_world = Rz(yaw)·v_device and v = (hx, hy) the horizontal
    field, we want Rz(yaw)·v aligned with world North (+Y):
    ``yaw = atan2(hx, hy)``. Verified on synthetic geometries in the test suite.
    """
    hx, hy = np.asarray(hx, dtype=float), np.asarray(hy, dtype=float)
    return np.arctan2(hx, hy)


def magnetometer_quality(mag_magnitude: np.ndarray) -> np.ndarray:
    """Per-sample heading quality: 'high' | 'medium' | 'low' | 'unavailable'.

    Uses the Earth-field magnitude band (per :data:`MAG_FIELD_MIN_UT` /
    :data:`MAG_FIELD_MAX_UT`) as a reality check; anything outside the band is
    suspicious (ferromagnetic disturbance / broken sensor).
    """
    mmag = np.asarray(mag_magnitude, dtype=float)
    valid = np.isfinite(mmag)
    out = np.full_like(mmag, "unavailable", dtype=object)
    ok_band = valid & (mmag >= MAG_FIELD_MIN_UT) & (mmag <= MAG_FIELD_MAX_UT)
    near_band = valid & ~ok_band & (mmag >= 10.0) & (mmag <= 200.0)
    out[ok_band] = "high"
    out[near_band] = "medium"
    out[valid & ~ok_band & ~near_band] = "low"
    return out


# --------------------------------------------------------------------------- #
# Complementary filter estimator                                               #
# --------------------------------------------------------------------------- #


@dataclass
class OrientationResult:
    """Output of :class:`OrientationEstimator.estimate`."""

    frame: pd.DataFrame
    columns: Tuple[str, ...] = ORIENTATION_COLUMNS
    config: Dict[str, object] = field(default_factory=dict)
    message: str = ""


class OrientationEstimator:
    """Practical device attitude estimator (complementary filter).

    Parameters
    ----------
    fusion_gain : float in (0, 1]. Weight of the accel/mag 'measurement' when
        blended against the gyro prediction each sample. ~0.05-0.2 is sane.
    ema_tau_s : seconds for the built-in accelerometer low-pass used to derive
        the gravity vector when explicit gravity columns are not supplied.
    mag_field (min_ut, max_ut) : Earth-field band for magnetometer quality.
    compensate_external_accel : if False, tilt uses the fused/quasi-static
        gravity as-is (recommended with GravityEstimator low-pass output).
    """

    def __init__(
        self,
        fusion_gain: float = 0.1,
        ema_tau_s: float = 1.0,
        mag_field: Tuple[float, float] = (MAG_FIELD_MIN_UT, MAG_FIELD_MAX_UT),
    ):
        if not 0.0 < fusion_gain <= 1.0:
            raise ValueError(f"fusion_gain must be in (0, 1], got {fusion_gain}")
        self.fusion_gain = float(fusion_gain)
        self.ema_tau_s = float(ema_tau_s)
        self.mag_field = tuple(float(m) for m in mag_field)

    @property
    def config(self) -> Dict[str, object]:
        return {
            "method": "complementary",
            "fusion_gain": self.fusion_gain,
            "ema_tau_s": self.ema_tau_s,
            "mag_field_min_ut": self.mag_field[0],
            "mag_field_max_ut": self.mag_field[1],
        }

    # ------------------------------------------------------------------ #

    def estimate(
        self,
        df: pd.DataFrame,
        accel: Optional[Sequence[str]] = None,
        gyro: Optional[Sequence[str]] = None,
        mag: Optional[Sequence[str]] = None,
        gravity: Optional[Sequence[str]] = None,
    ) -> OrientationResult:
        """Add orientation columns to a canonical frame.

        ``accel = [x, y, z]`` canonical accelerometer column names, likewise
        ``gyro`` / ``mag``. ``gravity`` optionally provides pre-computed gravity
        axes (``gravity_est_x`` etc.); otherwise a per-axis EMA of the
        accelerometer is used. Raw inputs are never modified.
        """
        out = df.copy()
        cfg = self.config

        ax = _col(out, accel or [ACCEL_X, ACCEL_Y, ACCEL_Z], 0)
        ay = _col(out, accel or [ACCEL_X, ACCEL_Y, ACCEL_Z], 1)
        az = _col(out, accel or [ACCEL_X, ACCEL_Y, ACCEL_Z], 2)
        gx = _col(out, gyro or [GYRO_X, GYRO_Y, GYRO_Z], 0)
        gy = _col(out, gyro or [GYRO_X, GYRO_Y, GYRO_Z], 1)
        gz = _col(out, gyro or [GYRO_X, GYRO_Y, GYRO_Z], 2)
        mx = _col(out, mag or [MAG_X, MAG_Y, MAG_Z], 0)
        my = _col(out, mag or [MAG_X, MAG_Y, MAG_Z], 1)
        mz = _col(out, mag or [MAG_X, MAG_Y, MAG_Z], 2)

        n = len(out)
        ts = (
            pd.to_numeric(out[TS_SEC], errors="coerce").to_numpy()
            if TS_SEC in out.columns
            else np.arange(n, dtype=float) / 10.0
        )
        ts = np.asarray(ts, dtype=float)

        # gravity reference: prefer provided columns, else EMA of accelerometer
        if gravity and all(g in out.columns for g in gravity):
            gvx = pd.to_numeric(out[gravity[0]], errors="coerce").to_numpy()
            gvy = pd.to_numeric(out[gravity[1]], errors="coerce").to_numpy()
            gvz = pd.to_numeric(out[gravity[2]], errors="coerce").to_numpy()
        else:
            gvx, gvy, gvz = _ema_gravity(ax, ay, az, ts, self.ema_tau_s)

        roll, pitch = roll_pitch_from_gravity(gvx, gvy, gvz)
        hx, hy, hz = tilt_compensated_magnetometer(mx, my, mz, roll, pitch)
        yaw_mag = magnetometer_heading_from_horizontal(hx, hy)
        mag_mag = np.sqrt(mx**2 + my**2 + mz**2)
        mag_q = magnetometer_quality(mag_mag)

        tilt_ok = np.isfinite(roll) & np.isfinite(pitch)
        # per-sample measurement attitude
        q_meas = np.empty((n, 4))
        q_meas[:] = np.nan
        for k in range(n):
            if tilt_ok[k]:
                g = np.array([gvx[k], gvy[k], gvz[k]])
                gnorm = np.linalg.norm(g)
                if gnorm > 1e-6:
                    qt = quat_from_two_vectors(g / gnorm, [0.0, 0.0, 1.0])
                    if mag_q[k] == "high" and np.isfinite(yaw_mag[k]):
                        qz = quat_from_axis_angle([0.0, 0.0, 1.0], float(yaw_mag[k]))
                        q_meas[k] = quat_normalize(quat_multiply(qz, qt))
                    else:
                        q_meas[k] = qt

        # run the complementary filter forward
        q_hist = np.empty((n, 4))
        q = None
        alpha = self.fusion_gain
        for k in range(n):
            if k > 0:
                dt = float(ts[k] - ts[k - 1])
                dt = min(max(dt, 0.0), 0.5)
            else:
                dt = 0.0
            omega = np.array([gx[k], gy[k], gz[k]])
            if q is None:
                q = q_meas[k] if np.isfinite(q_meas[k]).all() else np.array([1.0, 0.0, 0.0, 0.0])
            else:
                if np.isfinite(omega).all() and dt > 0:
                    dq = 0.5 * quat_multiply(q, np.concatenate([[0.0], omega])) * dt
                    q_pred = quat_normalize(q + dq)
                else:
                    q_pred = q
                if np.isfinite(q_meas[k]).all():
                    q = slerp(q_pred, q_meas[k], alpha)
                else:
                    q = q_pred
            q_hist[k] = q

        ew, ex, ey, ez = q_hist.T
        ep = np.degrees(np.array([quat_to_euler(q) for q in q_hist]))
        e_roll, e_pitch, e_yaw = ep[:, 2], ep[:, 1], ep[:, 0]

        heading_valid = np.isfinite(yaw_mag) & (mag_q == "high")
        source = np.full(n, "gyro", dtype=object)
        quality = np.full(n, "low", dtype=object)
        source[heading_valid] = "magnetometer"
        quality[heading_valid] = "high"
        tilt_present = tilt_ok
        tilt_quality = np.where(tilt_present, "good", "bad").astype(object)
        tilt_quality[~np.isfinite(gvx) & ~np.isfinite(gvy) & ~np.isfinite(gvz)] = "unavailable"
        # degrade to "medium" for field in the medium band but still valid
        medium = np.isfinite(yaw_mag) & (mag_q == "medium")
        source[medium & ~heading_valid] = "magnetometer"
        quality[medium & ~heading_valid] = "medium"

        out["orient_qw"] = ew
        out["orient_qx"] = ex
        out["orient_qy"] = ey
        out["orient_qz"] = ez
        out["orient_roll_deg"] = e_roll
        out["orient_pitch_deg"] = e_pitch
        out["orient_yaw_deg"] = e_yaw
        out["orient_heading_source"] = source
        out["orient_heading_quality"] = quality
        out["orient_tilt_quality"] = tilt_quality

        return OrientationResult(
            frame=out,
            columns=ORIENTATION_COLUMNS,
            config=cfg,
            message=(
                f"Orientation estimated over {n} samples "
                f"(heading: {np.mean(heading_valid):.0%} magnetometer-high)."
            ),
        )


# --------------------------------------------------------------------------- #
# internal helpers                                                             #
# --------------------------------------------------------------------------- #


def _col(df: pd.DataFrame, names: Sequence[str], i: int) -> np.ndarray:
    if len(names) != 3:
        raise ValueError(f"expected 3 column names, got {names!r}")
    name = names[i]
    if name not in df.columns:
        return np.full(len(df), np.nan)
    return pd.to_numeric(df[name], errors="coerce").to_numpy()


def _ema_gravity(
    ax: np.ndarray,
    ay: np.ndarray,
    az: np.ndarray,
    ts: np.ndarray,
    tau_s: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-axis EMA of acceleration; used as gravity stand-in when no explicit
    gravity columns are supplied. NaN gaps propagate (no fabrication)."""
    alpha = 1.0 / (1.0 + tau_s if tau_s > 0 else 1.0)
    results = []
    for a in (ax, ay, az):
        out = np.full_like(a, np.nan, dtype=float)
        prev = np.nan
        for k in range(len(a)):
            if len(ts) and not np.isfinite(ts[k]):
                prev = np.nan
                continue
            if not np.isfinite(a[k]):
                prev = np.nan
                continue
            if np.isfinite(prev):
                prev = (1.0 - alpha) * prev + alpha * a[k]
            else:
                prev = a[k]
            out[k] = prev
        results.append(out)
    return results[0], results[1], results[2]