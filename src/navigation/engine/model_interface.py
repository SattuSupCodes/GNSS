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

import logging

import numpy as np

from src.navigation.interfaces.messages import MLNavigationOutput

logger = logging.getLogger(__name__)

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


class TrainedMLInference(MLInference):
    """Runtime adapter wiring the trained navigation-side models (D-T3/D-T4/D-T5).

    Conceptual flow (the D-T3 -> D-T4 -> D-T5 -> navigation/fusion path):

        IMU window
          |
          +-> D-T3 vibration classifier
          |      used to shape measurement uncertainties (rough road =>
          |      the speed/accel corrections are trusted less) and to flag
          |      stationarity for speed pseudo-measurements
          |
          +-> D-T4 IMU-correction model
          |      predicts systematic forward-accel error -> rotated to ENU
          |      using the engine heading -> ``accel_correction_enu``
          |      (consumed by the filter's ``update_accel_correction``)
          |
          +-> D-T5 error model
                 predicts drift rate -> expected position error =
                 drift_rate * GNSS age -> ``position_error_m`` floor
                 (consumed by the engine confidence estimation)
          |
          v
        MLNavigationOutput -> engine.update_ml() -> filter/fusion state

    Every model degrades gracefully: a missing or unreadable artifact simply
    omits its contribution, so the engine keeps running classically.
    """

    def __init__(
        self,
        vibration_classifier: Optional[VibrationClassifier] = None,
        imu_correction_model: Optional[IMUCorrectionModel] = None,
        error_model: Optional[ErrorModel] = None,
        speed_model: Optional[SpeedModel] = None,
    ):
        from src.models.vibration_classifier.inference import (
            RandomForestVibrationClassifier,
        )
        from src.models.imu_correction.inference import (
            RandomForestIMUCorrectionModel,
        )
        from src.models.fusion_correction.inference import (
            RandomForestErrorModel,
        )

        self.vibration_classifier = vibration_classifier or RandomForestVibrationClassifier()
        self.imu_correction_model = imu_correction_model or RandomForestIMUCorrectionModel()
        self.error_model = error_model or RandomForestErrorModel()
        self.speed_model = speed_model

    @property
    def available(self) -> bool:
        return any(
            getattr(m, "available", False)
            for m in (
                self.vibration_classifier,
                self.imu_correction_model,
                self.error_model,
                self.speed_model,
            )
        )

    def bind(
        self,
        heading_provider=None,
        speed_provider=None,
        gnss_age_provider=None,
    ) -> "TrainedMLInference":
        """Wire live engine context into the sub-models (all optional)."""
        if hasattr(self.imu_correction_model, "set_heading_provider"):
            self.imu_correction_model.set_heading_provider(heading_provider)
        if hasattr(self.error_model, "set_speed_provider"):
            self.error_model.set_speed_provider(speed_provider)
        if hasattr(self.error_model, "set_gnss_age_provider"):
            self.error_model.set_gnss_age_provider(gnss_age_provider)
        return self

    def evaluate(self, timestamp: float, window: IMUWindow) -> MLNavigationOutput:
        vibration_class = None
        if getattr(self.vibration_classifier, "available", False):
            try:
                vibration_class = self.vibration_classifier.classify(window)
            except Exception as exc:  # noqa: BLE001
                logger.warning("D-T3 classify failed: %s", exc)

        speed_mps = None
        speed_std_mps = None
        if self.speed_model is not None:
            try:
                speed_mps, std = self.speed_model.predict_speed(window)
                speed_std_mps = std if std is not None else 1.0
            except Exception as exc:  # noqa: BLE001
                logger.warning("speed model failed: %s", exc)

        accel_correction_enu = None
        accel_correction_std_mps2 = None
        if getattr(self.imu_correction_model, "available", False):
            try:
                correction, std = self.imu_correction_model.predict_correction(window)
                if correction is not None:
                    accel_correction_enu = tuple(float(x) for x in correction)
                    accel_correction_std_mps2 = float(std) if std is not None else 1.0
            except Exception as exc:  # noqa: BLE001
                logger.warning("D-T4 predict_correction failed: %s", exc)

        position_error_m = None
        if getattr(self.error_model, "available", False):
            try:
                position_error_m, _conf = self.error_model.predict_error(window)
            except Exception as exc:  # noqa: BLE001
                logger.warning("D-T5 predict_error failed: %s", exc)

        # D-T3 consumption: vibration-rough roads make the learned acceleration
        # correction less reliable (inflate its std); stationary windows emit a
        # zero-speed pseudo-measurement so the filter holds position.
        if vibration_class == "vibration" and accel_correction_std_mps2 is not None:
            accel_correction_std_mps2 = 2.0 * accel_correction_std_mps2
        if vibration_class == "stationary":
            speed_mps = 0.0
            speed_std_mps = 0.2

        return MLNavigationOutput(
            timestamp=float(timestamp),
            speed_mps=speed_mps,
            speed_std_mps=speed_std_mps,
            accel_correction_enu=accel_correction_enu,
            accel_correction_std_mps2=accel_correction_std_mps2,
            position_error_m=position_error_m,
        )