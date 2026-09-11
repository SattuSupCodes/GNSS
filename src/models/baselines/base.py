"""Shared base class for classical speed-estimation baselines (D-T1)."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler


class ClassicalSpeedBaseline:
    """Fit/predict/save a classical regressor on causal per-timestep features.

    Subclasses set ``self.model`` (any sklearn-compatible estimator exposing
    ``fit(X, y)`` and ``predict(X)``).
    """

    name = "baseline"

    def __init__(self):
        self.scaler = StandardScaler()
        self.model = None

    # ------------------------------------------------------------------ #
    # Fitting
    # ------------------------------------------------------------------ #

    def fit(
        self,
        features_train: np.ndarray,
        targets_train: np.ndarray,
        mask_train: np.ndarray,
    ) -> "ClassicalSpeedBaseline":
        features = features_train[mask_train]
        targets = targets_train[mask_train]

        features = self.scaler.fit_transform(features)

        self.model.fit(features, targets)

        return self

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #

    def predict(
        self,
        features: np.ndarray,
    ) -> np.ndarray:
        """Predict one window (T, 3*C) -> per-timestep speeds (T,) in km/h."""
        features = np.asarray(features, dtype=np.float32)

        flat = features.reshape(-1, features.shape[-1])

        scaled = self.scaler.transform(flat)

        predicted = self.model.predict(scaled)

        predicted = np.maximum(predicted, 0.0)

        return predicted.reshape(features.shape[:2])

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump(self, path)

    @classmethod
    def load(cls, path) -> "ClassicalSpeedBaseline":
        return joblib.load(path)