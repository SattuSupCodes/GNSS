"""D-T4 runtime adapter: Random Forest IMU-correction model.

Implements the backend ``IMUCorrectionModel`` contract. The trained model
predicts the systematic *forward* acceleration error from an IMU window; the
adapter rotates it to ENU using the current engine heading (injected via
``set_heading_provider``) and returns ``(accel_correction_enu, std_mps2)``.

Falls back to ``(None, None)`` when the artifact is missing or no heading is
available so the navigation engine keeps running classically.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

from src.models import ml_common as mc
from src.navigation.engine.model_interface import IMUCorrectionModel

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT = Path("models/imu_correction.joblib")
DEFAULT_STD_MPS2 = 1.0
HeadingProvider = Callable[[], float]


class RandomForestIMUCorrectionModel(IMUCorrectionModel):
    """Artifact-backed longitudinal IMU-correction model."""

    def __init__(
        self,
        artifact_path: str | Path | None = None,
        std_mps2: float = DEFAULT_STD_MPS2,
        heading_provider: Optional[HeadingProvider] = None,
    ):
        self.artifact_path = Path(artifact_path or DEFAULT_ARTIFACT)
        self.std_mps2 = float(std_mps2)
        self._model = None
        self.heading_provider = heading_provider
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

    def set_heading_provider(self, provider: Optional[HeadingProvider]) -> None:
        self.heading_provider = provider

    def _heading_rad(self) -> Optional[float]:
        if self.heading_provider is None:
            return None
        try:
            h = float(self.heading_provider())
            return h if math.isfinite(h) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("heading provider failed: %s", exc)
            return None

    def predict_correction(
        self,
        window,
    ) -> Tuple[Optional[np.ndarray], Optional[float]]:
        """Return ``(accel_correction_enu, std_mps2)`` or ``(None, None)``."""
        if self._model is None:
            return None, None
        heading = self._heading_rad()
        if heading is None:
            return None, None

        windows = np.asarray(window, dtype=np.float64)
        if windows.ndim == 2:
            windows = windows[np.newaxis, ...]
        features, _ = mc.compute_window_features(windows)

        corr_forward = float(mc.predict_forest(self._model, features)[0])

        east = corr_forward * math.sin(heading)
        north = corr_forward * math.cos(heading)
        return np.asarray([east, north], dtype=np.float64), self.std_mps2