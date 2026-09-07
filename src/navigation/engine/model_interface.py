"""AI / ML integration interface (D-S7).

This module defines the *contract* between the navigation backend and
Tanishk's learned components (D-T2 speed model, D-T4 IMU correction model,
D-T3 vibration classifier, D-T5 error model).

The engine consumes ``MLNavigationOutput`` messages (defined in
``navigation/interfaces/messages.py``). The adapters below let trained
models be wrapped behind a small, stable interface. Until the models are
delivered, ``FallbackMLInference`` produces no corrections, so the engine
runs purely classically.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

import numpy as np

from src.navigation.interfaces.messages import MLNavigationOutput

#: A sliding IMU window: shape ``(n_windows, window_len, 6)`` with columns
#: [ax, ay, az, gx, gy, gz] (already calibrated, gravity compensated).
IMUWindow = np.ndarray

#: (correction_east, correction_north) in m/s^2.
Vec2T = Tuple[float, float]

#: Context classes produced by the vibration/context classifier.
VIBRATION_CLASSES = (
    "stationary",
    "smooth_road",
    "rough_road",
    "urban",
    "highway",
)


class SpeedModel(ABC):
    """Learned vehicle-speed estimator (D-T2)."""

    @abstractmethod
    def predict_speed(
        self,
        window: IMUWindow,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return ``(speed_mps, std_mps)`` or ``(None, None)`` if unsure."""


class IMUCorrectionModel(ABC):
    """Learned IMU error-correction model (D-T4)."""

    @abstractmethod
    def predict_correction(
        self,
        window: IMUWindow,
    ) -> Tuple[Optional[Vec2T], Optional[float]]:
        """Return ``(accel_correction_enu, std_mps2)``."""


class ErrorModel(ABC):
    """Optional learned navigation-error model (D-T5)."""

    @abstractmethod
    def predict_error(
        self,
        window: IMUWindow,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return ``(position_error_m, confidence)``."""


class VibrationClassifier(ABC):
    """Learned surface/vehicle context classifier (D-T3)."""

    @abstractmethod
    def classify(self, window: IMUWindow) -> str:
        """Return one of :data:`VIBRATION_CLASSES`."""


class MLInference(ABC):
    """Top-level adapter producing navigation-ready ML outputs (D-T10)."""

    @abstractmethod
    def evaluate(self, timestamp: float, window: IMUWindow) -> MLNavigationOutput:
        """Combine learned models into a single :class:`MLNavigationOutput`."""


class FallbackMLInference(MLInference):
    """No-op ML adapter used until the learned models are delivered (D-T7).

    Returns an empty :class:`MLNavigationOutput` so the fusion engine keeps
    running in its classical config (works with both EKF and UKF).
    """

    def evaluate(self, timestamp: float, window: IMUWindow) -> MLNavigationOutput:
        return MLNavigationOutput(timestamp=float(timestamp))


class CompositeMLInference(MLInference):
    """Wrap a set of trained sub-models into one :class:`MLInference`.

    Useful for wiring Tanishk's delivered checkpoints (D-T9/D-T10) without
    changes to the navigation backend.
    """

    def __init__(
        self,
        speed_model: Optional[SpeedModel] = None,
        imu_correction_model: Optional[IMUCorrectionModel] = None,
        error_model: Optional[ErrorModel] = None,
        vibration_classifier: Optional[VibrationClassifier] = None,
    ):
        self.speed_model = speed_model
        self.imu_correction_model = imu_correction_model
        self.error_model = error_model
        self.vibration_classifier = vibration_classifier

    def evaluate(self, timestamp: float, window: IMUWindow) -> MLNavigationOutput:
        output = MLNavigationOutput(timestamp=float(timestamp))

        if self.speed_model is not None:
            speed, std = self.speed_model.predict_speed(window)
            output.speed_mps = speed
            output.speed_std_mps = std

        if self.imu_correction_model is not None:
            correction, std = self.imu_correction_model.predict_correction(window)
            output.accel_correction_enu = correction

        return output