"""D-T3 runtime adapter: Random Forest vibration classifier.

Implements the backend ``VibrationClassifier`` contract
(``src/navigation/engine/model_interface.py``). Missing/broken artifacts fall
back gracefully to ``"normal"`` so the navigation engine never crashes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from src.models import ml_common as mc
from src.models.vibration_classifier.dataset import CLASSES
from src.navigation.engine.model_interface import VibrationClassifier

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT = Path("models/vibration_classifier.joblib")
FALLBACK_CLASS = "normal"


class RandomForestVibrationClassifier(VibrationClassifier):
    """Artifact-backed vibration classifier with graceful fallback."""

    def __init__(self, artifact_path: str | Path | None = None):
        self.artifact_path = Path(artifact_path or DEFAULT_ARTIFACT)
        self._model = None
        self._feature_names: Optional[list[str]] = None
        if self.artifact_path.exists():
            import joblib

            try:
                self._model = joblib.load(self.artifact_path)
                # Single-row runtime predict must stay on the serial path:
                # threaded joblib adds ~40 ms lock-sleep per call.
                self._model.n_jobs = 1
                self._feature_names = getattr(self._model, "feature_names_in_", None)
                if self._feature_names is not None:
                    self._feature_names = list(self._feature_names)
            except Exception as exc:  # noqa: BLE001 - ever-safe fallback
                logger.warning("Could not load %s: %s", self.artifact_path, exc)
                self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def classify(self, window) -> str:
        """Classify one IMU window ``(WINDOW_SIZE, 6)`` (or 3-D batched)."""
        if self._model is None:
            return FALLBACK_CLASS
        windows = np.asarray(window, dtype=np.float64)
        if windows.ndim == 2:
            windows = windows[np.newaxis, ...]
        features, _ = mc.compute_window_features(windows)
        preds = mc.predict_forest(self._model, features)
        return CLASSES[int(preds[0])]

    def classify_probabilities(self, window) -> dict[str, float]:
        """Class probabilities (useful for downstream uncertainty shaping)."""
        if self._model is None:
            return {c: (1.0 if c == FALLBACK_CLASS else 0.0) for c in CLASSES}
        windows = np.asarray(window, dtype=np.float64)
        if windows.ndim == 2:
            windows = windows[np.newaxis, ...]
        features, _ = mc.compute_window_features(windows)
        probs = self._model.predict_proba(features)[0]
        return {c: float(p) for c, p in zip(CLASSES, probs)}