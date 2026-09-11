"""Position error / uncertainty helpers (D-S10).

Converts filter covariance into the scalar estimates reported by the
navigation state and the confidence estimator. For a 2-D horizontal error
with standard deviations ``sigma_e`` and ``sigma_n`` the circular error
probable (CEP) treatments below assume a near-isotropic distribution,
which holds approximately for a fused GNSS+INS solution.
"""

from __future__ import annotations

import math

import numpy as np


def position_std_m(P) -> float:
    """Robust scalar position error estimate ``sqrt(tr(P_2d))``."""
    P = np.asarray(P, dtype=float)
    return float(math.sqrt(max(P[0, 0] + P[1, 1], 0.0)))


def position_std_isotropic_m(P) -> float:
    """Mean horizontal sigma for an isotropic assumption."""
    P = np.asarray(P, dtype=float)
    return float(math.sqrt(max(0.5 * (P[0, 0] + P[1, 1]), 0.0)))


def cep50_m(sigma: float) -> float:
    """Radius containing 50% of positions for a 2-D normal error."""
    return float(sigma) * math.sqrt(2.0 * math.log(2.0))


def cep95_m(sigma: float) -> float:
    """Radius containing 95% of positions for a 2-D normal error."""
    return float(sigma) * 2.4477


def radius_for_probability_m(sigma: float, probability: float) -> float:
    """Radius for a given probability under 2-D Gaussian error."""
    prob = min(max(float(probability), 0.0), 0.999999)
    return float(sigma) * math.sqrt(-2.0 * math.log(1.0 - prob))


def confidence_from_error(
    position_error_m: float,
    reference_error_m: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """Monotonic [0,1] confidence from an estimated position error.

    ``conf = exp(-error / reference_error)`` so that an error equal to the
    reference threshold maps to ``~0.37``.
    """
    if not math.isfinite(float(position_error_m)):
        return float(minimum)
    confidence = math.exp(
        -float(position_error_m) / max(float(reference_error_m), 1e-6)
    )
    return float(min(max(confidence, minimum), maximum))