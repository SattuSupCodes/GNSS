"""D-T5 runtime adapter: Random Forest navigation-error model.

Implements the backend ``ErrorModel`` contract. Predicts the *drift rate*
(m/s) from an IMU window + the current estimated speed (injected via
providers), and converts it to an expected position error using the current
GNSS age:

    expected_position_error_m = drift_rate * gnss_age

This flows into the engine's confidence as an error floor during outages.
Missing artifacts fall back to ``(None, None)`` (engine runs classically).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

from src.models import ml_common as mc
from src.navigation.engine.model_interface import ErrorModel

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT = Path("models/error_model.joblib")
DEFAULT_CONFIDENCE_REFERENCE_M = 50.0
ValueProvider = Callable[[], float]


class RandomForestErrorModel(ErrorModel):
    """Artifact-backed drift-rate / expected-position-error model."""

    def __init__(
        self,
        artifact_path: str | Path | None = None,
        speed_provider: Optional[ValueProvider] = None,
        gnss_age_provider: Optional[ValueProvider] = None,
        confidence_reference_m: float = DEFAULT_CONFIDENCE_REFERENCE_M,
    ):
        self.artifact_path = Path(artifact_path or DEFAULT_ARTIFACT)
        self.speed_provider = speed_provider
        self.gnss_age_provider = gnss_age_provider
        self.confidence_reference_m = float(confidence_reference_m)
        self._model = None
        if self.artifact_path.exists():
            import joblib

            try:
                self._model = joblib.load(self.artifact_path)
                # Single-row runtime predict must stay on the serial path:
                # threaded joblib adds ~40 ms lock-sleep per call.
                if hasattr(self._model, "n_jobs"):
                    self._model.n_jobs = 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load %s: %s", self.artifact_path, exc)
                self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def set_speed_provider(self, provider: Optional[ValueProvider]) -> None:
        self.speed_provider = provider

    def set_gnss_age_provider(self, provider: Optional[ValueProvider]) -> None:
        self.gnss_age_provider = provider

    def _provider_value(self, provider: Optional[ValueProvider]) -> float:
        if provider is None:
            return 0.0
        try:
            v = float(provider())
            return v if math.isfinite(v) else 0.0
        except Exception as exc:  # noqa: BLE001
            logger.warning("value provider failed: %s", exc)
            return 0.0

    def predict_error(
        self,
        window,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return ``(position_error_m, confidence)`` or ``(None, None)``."""
        if self._model is None:
            return None, None

        windows = np.asarray(window, dtype=np.float64)
        if windows.ndim == 2:
            windows = windows[np.newaxis, ...]
        features, _ = mc.compute_window_features(windows)
        speed = self._provider_value(self.speed_provider)
        row = np.concatenate([features[0], [speed]])

        drift = mc.predict_forest(self._model, row)  # scalar for a 1-D input
        drift_rate = max(float(np.asarray(drift).reshape(-1)[0]), 0.0)
        gnss_age = max(self._provider_value(self.gnss_age_provider), 0.0)
        if not np.isfinite(gnss_age):
            gnss_age = 0.0
        error_m = drift_rate * gnss_age
        confidence = math.exp(-error_m / self.confidence_reference_m)
        return error_m, confidence