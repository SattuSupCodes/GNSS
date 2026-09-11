"""AI / ML integration interface (D-S7 / D-T3 / D-T4 / D-T5).

This module defines the *contract* between the navigation backend and
the learned components:

    D-T2 speed model   -> ``TrainedSpeedModel`` (wraps LSTM / GRU / TCN)
    D-T3 vibration     -> ``RandomForestVibrationClassifier``
    D-T4 IMU correction -> ``RandomForestIMUCorrectionModel``
    D-T5 error model   -> ``RandomForestErrorModel``

``TrainedMLInference`` combines D-T3 + D-T4 + D-T5 into a single
``MLInference`` adapter: it consumes 6-channel calibrated IMU windows
(accel_x .. gyro_z), reads live engine state through providers bound
via ``bind()``, and returns a complete ``MLNavigationOutput``.

``CompositeMLInference`` (with ``TrainedSpeedModel``) handles the D-T2
speed-model integration exclusively (9-channel ``*_cal`` windows).

``FallbackMLInference`` produces no corrections so the engine runs
purely classically while models are unavailable.
"""

from __future__ import annotations

import dataclasses
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple

import logging

import numpy as np

from src.navigation.interfaces.messages import MLNavigationOutput

logger = logging.getLogger("gnss.ml")

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
            output = dataclasses.replace(
                output,
                speed_mps=speed,
                speed_std_mps=std,
            )

        if self.imu_correction_model is not None:
            correction, std = self.imu_correction_model.predict_correction(window)
            output = dataclasses.replace(
                output,
                accel_correction_enu=correction,
            )

        return output


# ====================================================================== #
# Trained speed-model adapter (D-T2)
# ====================================================================== #

#: Trained-artifact registry used by :func:`build_ml_inference`.
TRAINED_SPEED_MODELS = {
    "lstm": ("models/speed_lstm.pt", "models/speed_lstm_scaler.npz"),
    "gru": ("models/speed_gru.pt", "models/speed_gru_scaler.npz"),
    "tcn": ("models/speed_tcn.pt", "models/speed_tcn_scaler.npz"),
}


class TrainedSpeedModel(SpeedModel):
    """Wrap a trained ``SpeedEstimator`` behind the engine's ``SpeedModel``.

    Paths are resolved relative to the repository root so the adapter keeps
    working regardless of the caller's working directory. When the model
    cannot be loaded (missing/scorrupt artifact, wrong window shape) the
    adapter logs a warning and returns ``(None, None)``; the navigation
    backend then simply ignores the ML output - it never crashes because an
    ML model is unavailable.
    """

    def __init__(
        self,
        model_path: str | Path = "models/speed_lstm.pt",
        scaler_path: str | Path = "models/speed_lstm_scaler.npz",
        sequence_length: int = 100,
        repo_root: str | Path | None = None,
    ):
        self.repo_root = Path(repo_root) if repo_root else None

        self.model_path = self._resolve(model_path)
        self.scaler_path = self._resolve(scaler_path)
        self.sequence_length = int(sequence_length)

        self._estimator = None
        self._load_error: Optional[str] = None

    def _resolve(self, path: str | Path) -> Path:
        path = Path(path)
        if self.repo_root is not None:
            return self.repo_root / path
        if path.is_absolute() or path.exists():
            return path
        # Fall back to the repository root relative to this file.
        return Path(__file__).resolve().parents[3] / path

    def available(self) -> bool:
        """True when both artifact files exist (fast check)."""
        return self.model_path.exists() and self.scaler_path.exists()

    def _ensure_loaded(self):
        if self._estimator is not None:
            return self._estimator

        from src.models.speed_estimator.inference import SpeedEstimator

        try:
            self._estimator = SpeedEstimator(
                model_path=str(self.model_path),
                scaler_path=str(self.scaler_path),
            )
            logger.info(
                "Loaded trained speed model from %s",
                self.model_path,
            )
            return self._estimator
        except Exception as error:  # pragma: no cover - runtime safety net
            self._load_error = str(error)
            self._estimator = None
            logger.warning(
                "Speed model unavailable (%s): %s",
                self.model_path,
                error,
            )
            return None

    def predict_speed(
        self,
        window: IMUWindow,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Return ``(speed_mps, std_mps)`` or ``(None, None)`` if unsure."""
        try:
            arr = np.asarray(window, dtype=np.float32)

            if arr.ndim == 3 and arr.shape[0] == 1:
                arr = arr[0]

            expected = (self.sequence_length, 9)
            if arr.ndim != 2 or arr.shape != expected:
                logger.warning(
                    "Speed model window shape %s does not match %s",
                    arr.shape,
                    expected,
                )
                return (None, None)

            estimator = self._ensure_loaded()
            if estimator is None:
                return (None, None)

            prediction_kmh = estimator.predict(arr)

            prediction_kmh = np.asarray(
                prediction_kmh,
                dtype=np.float64,
            )

            if prediction_kmh.size == 0:
                return (None, None)

            prediction_kmh = np.nan_to_num(prediction_kmh)

            # km/h -> m/s; aggregate the per-timestep window to one scalar.
            mean_mps = float(np.mean(prediction_kmh)) / 3.6
            std_mps = float(np.std(prediction_kmh)) / 3.6

            return (mean_mps, std_mps)

        except Exception as error:
            logger.warning("Speed model inference failed: %s", error)
            return (None, None)


def build_ml_inference(
    ml_config: Optional[dict] = None,
    repo_root: str | Path | None = None,
) -> MLInference:
    """Build the runtime ``MLInference`` from a config dict (``ml:`` block).

    Rules:
        * disabled or no config   -> ``FallbackMLInference`` (current behavior)
        * unknown model name      -> ``FallbackMLInference``
        * artifact files missing  -> ``FallbackMLInference``
        * artifacts present       -> ``CompositeMLInference`` with the trained
          :class:`TrainedSpeedModel`; model loading is verified lazily and the
          adapter degrades to ``(None, None)`` on any inference error.
    """
    if not ml_config or not ml_config.get("enabled", False):
        return FallbackMLInference()

    model_name = str(ml_config.get("model", "lstm"))

    artifacts = TRAINED_SPEED_MODELS.get(model_name)

    if artifacts is None:
        logger.warning("Unknown ML model %r; using fallback.", model_name)
        return FallbackMLInference()

    model_path, scaler_path = artifacts

    if ml_config.get("model_path"):
        model_path = ml_config["model_path"]

    if ml_config.get("scaler_path"):
        scaler_path = ml_config["scaler_path"]

    speed_model = TrainedSpeedModel(
        model_path=model_path,
        scaler_path=scaler_path,
        sequence_length=int(ml_config.get("window_samples", 100)),
        repo_root=repo_root,
    )

    if not speed_model.available():
        logger.warning(
            "Trained speed model %r artifacts not found "
            "(%s); using fallback.",
            model_name,
            speed_model.model_path,
        )
        return FallbackMLInference()

    return CompositeMLInference(speed_model=speed_model)


# ====================================================================== #
# Trained navigation-ML inference (D-T3 + D-T4 + D-T5)
# ====================================================================== #

#: Default artifact paths (relative to the repository root) for the
#: navigation-side learned models.
TRAINED_CORRECTION_MODELS = {
    "vibration": "models/vibration_classifier.joblib",
    "imu_correction": "models/imu_correction.joblib",
    "error_model": "models/error_model.joblib",
}


class TrainedMLInference(MLInference):
    """Combine trained D-T3 / D-T4 / D-T5 artifacts into one ``MLInference``.

    Consumes 6-channel calibrated IMU windows ``(1, WINDOW_SIZE, 6)``
    (``accel_x..gyro_z``) - the exact layout the models were trained on.
    Live engine state is injected through the providers bound with
    :meth:`bind` (heading, speed, GNSS age); none of these providers leak
    reference/GNSS *truth* into the corridor - they are reads of the
    engine's own estimate.

    Runtime behaviour:

    * D-T3 ``stationary`` -> a 0 m/s pseudo-measurement (tight std).
    * D-T3 ``vibration`` -> accel-correction uncertainty inflated.
    * D-T4 -> ``accel_correction_enu`` (m/s^2, ENU) + ``std_mps2``.
    * D-T5 -> ``position_error_m`` = drift_rate * GNSS age (finite only;
      non-finite age degrades to 0 so ``inf``/``nan`` never propagates).

    When an artifact is missing/corrupt or inference raises, that field is
    simply omitted from the output - the engine runs classically and never
    crashes.
    """

    #: Pseudo-measurement uncertainty for the stationary speed update (m/s).
    STATIONARY_SPEED_STD_MPS = 0.1
    #: Multiplier applied to the accel-correction std in ``vibration``.
    VIBRATION_STD_MULTIPLIER = 2.0

    def __init__(
        self,
        vibration_path: str | Path | None = None,
        imu_correction_path: str | Path | None = None,
        error_model_path: str | Path | None = None,
        repo_root: str | Path | None = None,
    ):
        self.repo_root = Path(repo_root) if repo_root else None

        self._vibration = None
        self._imu_correction = None
        self._error_model = None

        config = {
            "vibration": vibration_path or TRAINED_CORRECTION_MODELS["vibration"],
            "imu_correction": (
                imu_correction_path or TRAINED_CORRECTION_MODELS["imu_correction"]
            ),
            "error_model": error_model_path or TRAINED_CORRECTION_MODELS["error_model"],
        }

        for key, factory in (
            (
                "vibration",
                self._load_vibration,
            ),
            (
                "imu_correction",
                self._load_imu_correction,
            ),
            (
                "error_model",
                self._load_error_model,
            ),
        ):
            try:
                setattr(self, f"_{key}", factory(config[key]))
            except Exception as error:  # noqa: BLE001 - never break the engine
                logger.warning("D-%s adapter unavailable (%s)", key, error)
                setattr(self, f"_{key}", None)

    # ------------------------------------------------------------------ #
    # Artifact loading (lazy imports keep engine startup light)
    # ------------------------------------------------------------------ #

    def _resolve(self, path: str | Path) -> Path | None:
        path = Path(path)
        if self.repo_root is not None:
            return self.repo_root / path
        if path.is_absolute() or path.exists():
            return path
        candidate = Path(__file__).resolve().parents[3] / path
        return candidate if candidate.exists() else path

    def _load_vibration(self, path):
        if not Path(path or "").exists() and not (self._resolve(path)).exists():
            return None
        from src.models.vibration_classifier.inference import (
            RandomForestVibrationClassifier,
        )

        return RandomForestVibrationClassifier(self._resolve(path))

    def _load_imu_correction(self, path):
        from src.models.imu_correction.inference import (
            RandomForestIMUCorrectionModel,
        )

        return RandomForestIMUCorrectionModel(self._resolve(path))

    def _load_error_model(self, path):
        from src.models.fusion_correction.inference import RandomForestErrorModel

        return RandomForestErrorModel(self._resolve(path))

    # ------------------------------------------------------------------ #
    # Providers (live engine state, no reference/GNSS-truth leakage)
    # ------------------------------------------------------------------ #

    def bind(
        self,
        heading_provider: Optional[callable] = None,
        speed_provider: Optional[callable] = None,
        gnss_age_provider: Optional[callable] = None,
    ) -> None:
        """Bind live engine state readers to the correction adapters."""
        if self._imu_correction is not None:
            self._imu_correction.set_heading_provider(heading_provider)
        if self._error_model is not None:
            self._error_model.set_speed_provider(speed_provider)
            self._error_model.set_gnss_age_provider(gnss_age_provider)

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #

    @property
    def available(self) -> bool:
        return any(
            adapter is not None
            for adapter in (self._vibration, self._imu_correction, self._error_model)
        )

    def _window(self, window: IMUWindow) -> Optional[np.ndarray]:
        """Normalize to ``(1, W, 6)``; a 9-channel speed window is trimmed."""
        windows = np.asarray(window, dtype=np.float64)
        if windows.ndim == 2:
            windows = windows[np.newaxis, :, :]
        if windows.ndim != 3 or windows.shape[1] < 2 or windows.shape[2] < 6:
            return None
        if windows.shape[2] > 6:
            windows = windows[:, :, :6]
        if not np.isfinite(windows).all():
            return None
        return windows

    def evaluate(self, timestamp: float, window: IMUWindow) -> MLNavigationOutput:
        output = MLNavigationOutput(timestamp=float(timestamp))
        if not self.available:
            return output

        windows = self._window(window)
        if windows is None:
            return output

        # D-T3 vibration / stationary context
        context = None
        if self._vibration is not None:
            try:
                context = self._vibration.classify(windows)
            except Exception as error:  # noqa: BLE001
                logger.warning("D-T3 classify failed: %s", error)
                context = None

        stationary = context == "stationary"
        vibration = context == "vibration"

        if stationary:
            # 0 m/s pseudo-measurement: the vehicle is detected at rest.
            output = dataclasses.replace(
                output,
                speed_mps=0.0,
                speed_std_mps=self.STATIONARY_SPEED_STD_MPS,
            )

        # D-T4 accel correction (rotated to ENU by the engine heading)
        if self._imu_correction is not None:
            try:
                correction, std = self._imu_correction.predict_correction(windows)
                if correction is not None and std is not None:
                    correction = np.asarray(correction, dtype=np.float64)
                    std = float(std)
                    if (
                        correction.shape == (2,)
                        and np.isfinite(correction).all()
                        and np.isfinite(std)
                    ):
                        if vibration:
                            std = std * self.VIBRATION_STD_MULTIPLIER
                        output = dataclasses.replace(
                            output,
                            accel_correction_enu=(
                                float(correction[0]),
                                float(correction[1]),
                            ),
                            accel_correction_std_mps2=float(std),
                        )
            except Exception as error:  # noqa: BLE001
                logger.warning("D-T4 prediction failed: %s", error)

        # D-T5 expected position error (drift rate * GNSS age); the adapter
        # guarantees a finite, non-negative age so no inf/nan reaches the
        # engine state.
        if self._error_model is not None:
            try:
                error_m, _confidence = self._error_model.predict_error(windows)
                if (
                    error_m is not None
                    and np.isfinite(error_m)
                    and float(error_m) >= 0.0
                ):
                    output = dataclasses.replace(
                        output,
                        position_error_m=float(error_m),
                    )
            except Exception as error:  # noqa: BLE001
                logger.warning("D-T5 prediction failed: %s", error)

        return output