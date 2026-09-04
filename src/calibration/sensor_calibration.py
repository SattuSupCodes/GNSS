"""Reusable smartphone sensor calibration utilities.

Covers accelerometer, gyroscope and magnetometer. The emphasis is on honest,
reusable building blocks, NOT laboratory-grade calibration:

* **bias estimation** — mean/median bias from static samples (gyro) or from the
  sphere-fit of diverse orientations (accel/mag).
* **scale / offset correction** — least-squares sphere fit for accel/mag
  (solves for per-axis scale and bias from measurements spread across many
  orientations).
* **calibration metadata** — every result records ``source`` ("estimated" |
  "configured"), method and fit quality so downstream code can distinguish
  *estimated* parameters from *configured* ones from *unavailable* ones.
* **calibration validation** — finite values, sane scale range, etc. before the
  profile is used.

Raw measurements are preserved: calibrated values go into separate columns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Calibration profile                                                          #
# --------------------------------------------------------------------------- #

SOURCE_ESTIMATED = "estimated"
SOURCE_CONFIGURED = "configured"
SOURCE_UNAVAILABLE = "unavailable"


@dataclass
class SensorCalibrationProfile:
    """One sensor's calibration model: ``cal = scale * (raw - bias) + offset``.

    * ``source == "estimated"`` : parameters were fit from data.
    * ``source == "configured"``: parameters came from configuration (may still
      be all zeros = "copy through").
    * ``source == "unavailable"``: no calibration known; ``calibrate`` leaves
      raw values untouched.
    """

    sensor: str
    bias: np.ndarray = field(default_factory=lambda: np.zeros(3))
    scale: np.ndarray = field(default_factory=lambda: np.ones(3))
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3))
    source: str = SOURCE_UNAVAILABLE
    method: str = ""
    fitted_samples: int = 0
    fit_error_mse: Optional[float] = None
    note: str = ""

    def __post_init__(self):
        self.bias = np.asarray(self.bias, dtype=float).reshape(-1)
        self.scale = np.asarray(self.scale, dtype=float).reshape(-1)
        self.offset = np.asarray(self.offset, dtype=float).reshape(-1)
        if self.source not in (SOURCE_ESTIMATED, SOURCE_CONFIGURED, SOURCE_UNAVAILABLE):
            raise ValueError(f"bad source {self.source!r}")

    def is_available(self) -> bool:
        return self.source != SOURCE_UNAVAILABLE and bool(
            np.isfinite(self.bias).all()
            and np.isfinite(self.scale).all()
            and np.isfinite(self.offset).all()
        )

    def calibrate(self, xyz: np.ndarray) -> np.ndarray:
        """Apply ``scale * (raw - bias) + offset`` to an ``(n, 3)`` array."""
        xyz = np.asarray(xyz, dtype=float)
        if xyz.ndim == 1:
            xyz = xyz.reshape(1, 3)
        if not self.is_available():
            return np.where(np.isfinite(xyz), xyz, np.nan).copy()
        out = self.scale * (xyz - self.bias) + self.offset
        out[~np.isfinite(xyz).all(axis=1)] = np.nan
        return out

    def to_dict(self) -> Dict[str, object]:
        return {
            "sensor": self.sensor,
            "bias": list(map(float, self.bias)),
            "scale": list(map(float, self.scale)),
            "offset": list(map(float, self.offset)),
            "source": self.source,
            "method": self.method,
            "fitted_samples": int(self.fitted_samples),
            "fit_error_mse": self.fit_error_mse,
            "note": self.note,
        }


def configured_profile(
    sensor: str,
    bias=None,
    scale=None,
    offset=None,
    note: str = "",
) -> SensorCalibrationProfile:
    """Build a ``source="configured"`` profile from explicit parameters."""
    return SensorCalibrationProfile(
        sensor=sensor,
        bias=np.zeros(3) if bias is None else np.asarray(bias, dtype=float),
        scale=np.ones(3) if scale is None else np.asarray(scale, dtype=float),
        offset=np.zeros(3) if offset is None else np.asarray(offset, dtype=float),
        source=SOURCE_CONFIGURED,
        method="configured",
        note=note,
    )


def unavailable_profile(sensor: str, note: str = "") -> SensorCalibrationProfile:
    return SensorCalibrationProfile(sensor=sensor, source=SOURCE_UNAVAILABLE, note=note)


def validate_profile(profile: SensorCalibrationProfile) -> Tuple[bool, str]:
    """Sanity-check a profile before applying it."""
    if not np.isfinite(profile.bias).all() or not np.isfinite(profile.scale).all() or not np.isfinite(profile.offset).all():
        return False, "non-finite parameters"
    if profile.scale.shape != (3,) or profile.bias.shape != (3,) or profile.offset.shape != (3,):
        return False, "expected length-3 vectors"
    if np.any(profile.scale <= 0.01) or np.any(profile.scale > 10.0):
        return False, f"scale out of sane range {profile.scale.tolist()}"
    return True, "ok"


# --------------------------------------------------------------------------- #
# Estimation                                                                   #
# --------------------------------------------------------------------------- #


def fit_sphere_ls(
    samples: np.ndarray, sensor: str = ""
) -> Tuple[Optional[SensorCalibrationProfile], Optional[Dict[str, object]]]:
    """Bias (center) of a triaxial sensor via a least-squares sphere fit.

    Model: ``|raw - bias| == radius`` (unit scale). Expands to
    ``x*Bx + y*By + z*Bz + D = -|xyz|^2`` and solves for ``B, D``; then
    ``bias = -B/2`` and ``radius = sqrt(|B|^2/4 - D)``.

    Requires enough samples spread over distinct orientations; a degenerate or
    poorly-conditioned geometry is reported as ``ok=False`` rather than trusted.
    Returns ``(profile, report)``; profile None when not trustworthy.
    """
    xyz = np.asarray(samples, dtype=float)
    valid = np.isfinite(xyz).all(axis=1)
    xyz = xyz[valid]
    n = len(xyz)
    if n < 8:
        return None, {"ok": False, "reason": "insufficient_samples", "n": n}
    A = np.column_stack([xyz, np.ones(n)])
    b_vec = -np.sum(xyz**2, axis=1)
    sol, _, rank, _ = np.linalg.lstsq(A, b_vec, rcond=None)
    B = sol[:3]
    D = float(sol[3])
    radius2 = np.dot(B, B) / 4.0 - D
    residual_mse = float(np.mean((A @ sol - b_vec) ** 2))
    bias = -B / 2.0
    if radius2 <= 0 or not np.isfinite(bias).all() or rank < 4:
        return None, {"ok": False, "reason": "degenerate_fit", "n": n, "rank": int(rank)}
    profile = SensorCalibrationProfile(
        sensor=sensor or "sensor",
        bias=bias,
        scale=np.ones(3),
        offset=np.zeros(3),
        source=SOURCE_ESTIMATED,
        method="least_squares_sphere_fit",
        fitted_samples=n,
        fit_error_mse=residual_mse,
        note="Unit-scale sphere fit: returns center (bias) and radius only.",
    )
    report = {
        "ok": True,
        "n": n,
        "rank": int(rank),
        "radius": float(np.sqrt(radius2)),
        "residual_mse": residual_mse,
    }
    return profile, report


def fit_ellipsoid_scale_bias(
    samples: np.ndarray, sensor: str = ""
) -> Tuple[Optional[SensorCalibrationProfile], Optional[Dict[str, object]]]:
    """Per-axis scale + bias via a normalized ellipsoid fit.

    Model: ``sum_i scale_i^2 * (raw_i - bias_i)^2 == const`` with the global
    magnitude factor NOT identifiable from shape alone -> normalized such that
    ``scale_x == 1``. Callers must handle the resulting arbitrary global scale;
    the profile's ``note`` records this caveat.

    Expands to ``x^2 + ry*y^2 + rz*z^2 + b0*x + b1*y + b2*z + b3 = 0`` and solves
    for ``[ry, rz, b0, b1, b2, b3]``. Requires diverse orientations.
    """
    xyz = np.asarray(samples, dtype=float)
    valid = np.isfinite(xyz).all(axis=1)
    xyz = xyz[valid]
    n = len(xyz)
    if n < 12:
        return None, {"ok": False, "reason": "insufficient_samples", "n": n}
    x, y, z = xyz.T
    A = np.column_stack([y**2, z**2, x, y, z, np.ones(n)])
    b_vec = -(x**2)
    sol, _, rank, _ = np.linalg.lstsq(A, b_vec, rcond=None)
    ry, rz = float(sol[0]), float(sol[1])
    b0, b1, b2 = sol[2], sol[3], sol[4]
    residual_mse = float(np.mean((A @ sol - b_vec) ** 2))
    if ry <= 0 or rz <= 0 or rank < 6:
        return None, {"ok": False, "reason": "not_ellipsoid", "n": n, "rank": int(rank)}
    scale = np.array([1.0, np.sqrt(ry), np.sqrt(rz)])
    bias = np.array([-b0 / 2.0, -b1 / (2.0 * ry), -b2 / (2.0 * rz)])
    if not np.isfinite(bias).all() or np.any(scale <= 0):
        return None, {"ok": False, "reason": "invalid_solution", "n": n}
    profile = SensorCalibrationProfile(
        sensor=sensor or "sensor",
        bias=bias,
        scale=scale,
        offset=np.zeros(3),
        source=SOURCE_ESTIMATED,
        method="normalized_ellipsoid_fit",
        fitted_samples=n,
        fit_error_mse=residual_mse,
        note="Per-axis scale + bias; global magnitude factor is NOT identifiable "
        "and was normalized to scale_x=1. Fine for shape correction, not for "
        "absolute magnitude.",
    )
    report = {
        "ok": True,
        "n": n,
        "rank": int(rank),
        "scale": scale.tolist(),
        "residual_mse": residual_mse,
    }
    return profile, report


def estimate_gyro_bias(static_samples: np.ndarray, sensor: str = "gyro") -> SensorCalibrationProfile:
    """Zero-rate gyro bias as the per-axis mean over (near-)static samples.

    No rate table is assumed: we only fix the bias so the resting gyro reads ~0.
    Scale/misalignment are out of scope (that would need controlled rotation).
    """
    xyz = np.asarray(static_samples, dtype=float)
    valid = np.isfinite(xyz).all(axis=1)
    xyz = xyz[valid]
    if len(xyz) < 2:
        return unavailable_profile(sensor, note="too few static gyro samples")
    bias = np.nanmean(xyz, axis=0)
    return SensorCalibrationProfile(
        sensor=sensor,
        bias=bias,
        scale=np.ones(3),
        offset=np.zeros(3),
        source=SOURCE_ESTIMATED,
        method="static_mean",
        fitted_samples=len(xyz),
        note="Zero-rate bias only; scale/misalignment not estimated.",
    )


# --------------------------------------------------------------------------- #
# DataFrame integration                                                        #
# --------------------------------------------------------------------------- #

_AXIS_NAMES = ("x", "y", "z")


def apply_calibration(
    df: pd.DataFrame,
    sensor: str,
    profile: SensorCalibrationProfile,
    base_cols: Optional[List[str]] = None,
    suffix: str = "_cal",
) -> pd.DataFrame:
    """Append calibrated columns ``<base>_cal`` for one sensor's x/y/z channels.

    ``base_cols`` defaults to ``[f'{sensor}_x', f'{sensor}_y', f'{sensor}_z']``.
    Raw columns are untouched. Works even when the profile is "unavailable"
    (columns are then copies of raw, so downstream code has a uniform shape).
    """
    if base_cols is None:
        base_cols = [f"{sensor}_{a}" for a in _AXIS_NAMES]
    missing = [c for c in base_cols if c not in df.columns]
    if missing:
        raise KeyError(f"missing base columns: {missing}")
    out = df.copy()
    raw = np.column_stack(
        [pd.to_numeric(out[c], errors="coerce").to_numpy() for c in base_cols]
    )
    cal = profile.calibrate(raw)
    for i, c in enumerate(base_cols):
        out[c + suffix] = cal[:, i]
    return out


def calibration_metadata_for(
    profiles: Dict[str, SensorCalibrationProfile],
) -> Dict[str, object]:
    """Serialisable metadata block describing a set of sensor profiles."""
    return {name: p.to_dict() for name, p in profiles.items()}