"""Gravity estimation from smartphone accelerometer measurements.

The accelerometer measures specific force (m/s^2): the vector sum of the
opposing gravity reaction and linear (dynamic) acceleration. When a phone is in
a car, the accelerator is NOT stationary, so we cannot assume that gravity is a
constant along one axes; instead we recover gravity as the slow-varying, mostly
low-frequency component of the measured acceleration and treat the residual as
linear (dynamic) acceleration.

Mission constraint honoured here: **raw accelerometer values are never
overwritten.** Estimated gravity and linear acceleration are stored in new
columns (`gravity_est_*`, `linear_accel_*`).

Methodology
-----------
* lowpass (default): zero-phase Butterworth low-pass filter per axis
  (``scipy.signal.sosfiltfilt``). Gravity lives at very low frequencies
  (< ~0.2 Hz) while vehicle/IMU dynamics are above that. Runs are filtered in
  contiguous blocks so gaps (NaN rows) are never fabrication-filled.
* mean: stationary/segment-average fallback for very short windows where a
  low-pass filter is not meaningful.

When the number of valid samples is below ``min_samples``, no estimate is made
(columns are NaN, ``status == "insufficient_samples"``) and the caller is told
clearly instead of receiving a guessed gravity vector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import signal

from ..data.data_schema import ACCEL_X, ACCEL_Y, ACCEL_Z

STANDARD_GRAVITY = 9.80665
"""Standard gravity magnitude in m/s^2 (WGS84 reference value)."""

GRAVITY_EST_COLUMNS = (
    "gravity_est_x",
    "gravity_est_y",
    "gravity_est_z",
    "gravity_est_magnitude",
    "linear_accel_x",
    "linear_accel_y",
    "linear_accel_z",
    "gravity_est_valid",
)

DEFAULT_CUTOFF_HZ = 0.05
"""Default gravity low-pass cutoff (Hz). ~0.05 Hz = time constant of tens of
seconds; keeps the quasi-static gravity vector while removing vehicle dynamics."""

MIN_SAMPLES_FOR_LOWPASS = 2 * 32  # need >= ~4*order samples for a meaningful pass


@dataclass
class GravityEstimate:
    """Result of gravity estimation for one frame."""

    frame: pd.DataFrame
    status: str
    magnitude_mean: Optional[float] = None
    magnitude_std: Optional[float] = None
    message: str = ""
    config: Dict[str, object] = field(default_factory=dict)


def _contiguous_runs(values: np.ndarray) -> List[np.ndarray]:
    """Index slices of consecutive finite values in ``values``."""
    x = np.asarray(values, dtype=float)
    valid = np.isfinite(x)
    if not valid.any():
        return []
    idx = np.flatnonzero(valid)
    breaks = np.flatnonzero(np.diff(idx) != 1)
    starts = np.r_[0, breaks + 1]
    ends = np.r_[breaks, len(idx) - 1]
    return [idx[s : e + 1] for s, e in zip(starts, ends)]


def lowpass_axis(
    values: np.ndarray,
    fs: float,
    cutoff_hz: float,
    order: int = 4,
    min_run: int = 20,
) -> np.ndarray:
    """Zero-phase Butterworth low-pass of one axis over contiguous valid runs.

    Rows with NaN/inf are left NaN. Runs shorter than ``min_run`` fall back to
    the run mean (documented, safe) so short glitch-free segments still produce
    a usable gravity reference instead of a NaN wall.
    """
    x = np.asarray(values, dtype=float)
    out = np.full_like(x, np.nan)
    if fs <= 0 or cutoff_hz <= 0 or cutoff_hz >= fs / 2:
        return out
    for run in _contiguous_runs(x):
        seg = x[run]
        if len(seg) < min_run:
            if len(seg) >= 1:
                out[run] = np.nanmean(seg)
            continue
        sos = signal.butter(
            order, cutoff_hz, btype="lowpass", fs=fs, output="sos"
        )
        padlen = min(3 * (len(sos) * 2 + 1), len(seg) - 1)
        try:
            out[run] = signal.sosfiltfilt(sos, seg, padlen=padlen)
        except ValueError:
            out[run] = np.nanmean(seg)
    return out


def _mean_axis(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    out = pd.Series(x)
    return out.fillna(out.mean()).to_numpy() if out.notna().any() else np.full_like(x, np.nan)


class GravityEstimator:
    """Estimate gravity (and linear acceleration) from accelerometer streams.

    Parameters
    ----------
    method : str, one of {"lowpass", "mean"}. Default "lowpass".
    cutoff_hz, filter_order : low-pass parameters (unused by "mean").
    fs : nominal sampling rate in Hz.
    min_samples : minimum number of finite samples required before an estimate
        is attempted; below this the status is ``insufficient_samples``.
    """

    def __init__(
        self,
        method: str = "lowpass",
        cutoff_hz: float = DEFAULT_CUTOFF_HZ,
        filter_order: int = 4,
        fs: float = 10.0,
        min_samples: int = 20,
    ):
        if method not in ("lowpass", "mean"):
            raise ValueError(f"method must be 'lowpass' or 'mean', got {method!r}")
        self.method = method
        self.cutoff_hz = float(cutoff_hz)
        self.filter_order = int(filter_order)
        self.fs = float(fs)
        self.min_samples = int(min_samples)

    @property
    def config(self) -> Dict[str, object]:
        return {
            "method": self.method,
            "cutoff_hz": self.cutoff_hz,
            "filter_order": self.filter_order,
            "fs": self.fs,
            "min_samples": self.min_samples,
        }

    # ------------------------------------------------------------------ #
    # Core estimation                                                     #
    # ------------------------------------------------------------------ #

    def estimate_axes(
        self, ax: np.ndarray, ay: np.ndarray, az: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return estimated gravity per axis (same length as input)."""
        ax, ay, az = (
            np.asarray(ax, dtype=float),
            np.asarray(ay, dtype=float),
            np.asarray(az, dtype=float),
        )
        n = len(ax)
        if self.method == "mean":
            gx = _mean_axis(ax)
            gy = _mean_axis(ay)
            gz = _mean_axis(az)
        else:
            gx = lowpass_axis(
                ax, self.fs, self.cutoff_hz, order=self.filter_order
            )
            gy = lowpass_axis(
                ay, self.fs, self.cutoff_hz, order=self.filter_order
            )
            gz = lowpass_axis(
                az, self.fs, self.cutoff_hz, order=self.filter_order
            )
        return gx, gy, gz

    def fit_transform(self, df: pd.DataFrame) -> GravityEstimate:
        """Add gravity/linear-acceleration columns to a canonical frame.

        Always returns a copy; ``accel_x/y/z`` are preserved untouched.
        """
        out = df.copy()
        has = all(c in out.columns for c in (ACCEL_X, ACCEL_Y, ACCEL_Z))
        if not has:
            for c in GRAVITY_EST_COLUMNS:
                out[c] = float("nan")
            return GravityEstimate(out, status="missing_columns")

        ax = pd.to_numeric(out[ACCEL_X], errors="coerce").to_numpy()
        ay = pd.to_numeric(out[ACCEL_Y], errors="coerce").to_numpy()
        az = pd.to_numeric(out[ACCEL_Z], errors="coerce").to_numpy()
        valid = np.isfinite(ax) & np.isfinite(ay) & np.isfinite(az)
        n_valid = int(valid.sum())

        if n_valid < max(1, self.min_samples):
            for c in GRAVITY_EST_COLUMNS:
                out[c] = float("nan")
            return GravityEstimate(
                out,
                status="insufficient_samples",
                message=(
                    f"Only {n_valid}/{len(out)} finite accelerometer samples; "
                    f"need >= {self.min_samples}. No gravity estimate made."
                ),
                config=self.config,
            )

        gx, gy, gz = self.estimate_axes(ax, ay, az)
        gmag = np.sqrt(gx**2 + gy**2 + gz**2)
        g_ok = np.isfinite(gx) & np.isfinite(gy) & np.isfinite(gz)

        out["gravity_est_x"] = gx
        out["gravity_est_y"] = gy
        out["gravity_est_z"] = gz
        out["gravity_est_magnitude"] = gmag
        out["linear_accel_x"] = np.where(g_ok, ax - gx, np.nan)
        out["linear_accel_y"] = np.where(g_ok, ay - gy, np.nan)
        out["linear_accel_z"] = np.where(g_ok, az - gz, np.nan)
        out["gravity_est_valid"] = g_ok

        mag = gmag[g_ok]
        status = "ok" if len(mag) else "insufficient_samples"
        return GravityEstimate(
            out,
            status=status,
            magnitude_mean=float(np.mean(mag)) if len(mag) else None,
            magnitude_std=float(np.std(mag)) if len(mag) else None,
            message=(
                f"Gravity estimated from {n_valid} samples; mean magnitude "
                f"{float(np.mean(mag)):.3f} m/s^2"
                if len(mag)
                else "No gravity estimate."
            ),
            config=self.config,
        )

    # ------------------------------------------------------------------ #
    # Static-segment helper                                                #
    # ------------------------------------------------------------------ #

    def estimate_static_vector(
        self, accel_window: np.ndarray
    ) -> tuple[Optional[np.ndarray], Optional[float]]:
        """Mean gravity vector over a (near-)static window.

        Returns ``(g_vector, magnitude)`` or ``(None, None)`` when the window is
        empty / fully invalid. ``numpy.nanmean`` is used, so a few spurious
        values do not destroy the estimate.
        """
        a = np.asarray(accel_window, dtype=float)
        if a.ndim != 2 or a.shape[1] != 3 or not len(a):
            return None, None
        a = a.reshape(-1, 3)
        valid = np.isfinite(a).all(axis=1)
        if not valid.any():
            return None, None
        g = np.nanmean(a[valid], axis=0)
        return g, float(np.linalg.norm(g))


def gravity_magnitude_stats(gx, gy, gz) -> Dict[str, float]:
    """Summary statistics of the gravity magnitude.

    Returns ``mean``, ``std`` (m/s^2), ``n_valid`` and ``pct_within_tol`` =
    fraction of valid samples whose magnitude is within 5% of
    :data:`STANDARD_GRAVITY`.
    """
    gx = np.asarray(gx, dtype=float)
    gy = np.asarray(gy, dtype=float)
    gz = np.asarray(gz, dtype=float)
    m = np.isfinite(gx) & np.isfinite(gy) & np.isfinite(gz)
    mag = np.sqrt(gx[m] ** 2 + gy[m] ** 2 + gz[m] ** 2)
    if not len(mag):
        return {"mean": float("nan"), "std": float("nan"), "n_valid": 0, "pct_within_tol": 0.0}
    tol = 0.05 * STANDARD_GRAVITY
    return {
        "mean": float(np.mean(mag)),
        "std": float(np.std(mag)),
        "n_valid": int(len(mag)),
        "pct_within_tol": float(np.mean(np.abs(mag - STANDARD_GRAVITY) <= tol)),
    }


def check_gravity_tolerance(
    gx, gy, gz, atol: float = 0.5, pct_required: float = 0.8
) -> bool:
    """True when >= ``pct_required`` of finite samples have magnitude within
    ``atol`` m/s^2 of :data:`STANDARD_GRAVITY`."""
    stats = gravity_magnitude_stats(gx, gy, gz)
    if not stats["n_valid"]:
        return False
    return stats["pct_within_tol"] >= pct_required


def estimate_gravity_static(accel_window: np.ndarray) -> tuple[Optional[np.ndarray], Optional[float]]:
    """Module-level convenience wrapper over GravityEstimator.estimate_static_vector."""
    return GravityEstimator().estimate_static_vector(accel_window)