"""Inference utilities for the trained smartphone speed estimator."""

from pathlib import Path
from typing import Optional

import numpy as np
import torch

from src.models.speed_estimator.features import FeatureScaler
from src.models.speed_estimator.lstm import SpeedLSTM
from src.models.speed_estimator.gru import SpeedGRU
from src.models.speed_estimator.tcn import SpeedTCN


DEFAULT_MODEL_PATH = Path("models/speed_lstm.pt")
DEFAULT_SCALER_PATH = Path("models/speed_lstm_scaler.npz")

FEATURE_COLUMNS = [
    "accel_x_cal",
    "accel_y_cal",
    "accel_z_cal",
    "gyro_x_cal",
    "gyro_y_cal",
    "gyro_z_cal",
    "mag_x_cal",
    "mag_y_cal",
    "mag_z_cal",
]

MODEL_TYPES = {
    "lstm": SpeedLSTM,
    "gru": SpeedGRU,
    "tcn": SpeedTCN,
}


def build_model_from_checkpoint(checkpoint: dict):
    """Construct the right architecture from a saved checkpoint."""
    model_type = str(checkpoint.get("model_type", "lstm"))

    if model_type not in MODEL_TYPES:
        raise ValueError(
            f"Unknown model_type {model_type!r} in checkpoint"
        )

    model_class = MODEL_TYPES[model_type]

    if model_type in ("lstm", "gru"):
        return model_class(
            input_size=checkpoint.get("input_size", 9),
            hidden_size=checkpoint.get("hidden_size", 64),
            num_layers=checkpoint.get("num_layers", 2),
        )

    if model_type == "tcn":
        return model_class(
            input_size=checkpoint.get("input_size", 9),
            channels=checkpoint.get("channels", 32),
            dilations=tuple(checkpoint.get("dilations", [1, 2, 4, 8])),
        )

    raise ValueError(f"Unknown model type: {model_type}")


class SpeedEstimator:
    """Load a trained speed model and estimate speed from sensor sequences.

    Supports the LSTM, GRU and TCN checkpoints written by ``train.py``. The
    architecture is auto-detected from the checkpoint's ``model_type`` field
    (defaults to ``lstm`` for backward compatibility with the original
    artifact).
    """

    def __init__(
        self,
        model_path: str = str(DEFAULT_MODEL_PATH),
        scaler_path: str = str(DEFAULT_SCALER_PATH),
        device: Optional[str] = None,
    ):
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {self.model_path}"
            )

        if not self.scaler_path.exists():
            raise FileNotFoundError(
                f"Scaler not found: {self.scaler_path}"
            )

        # ----------------------------------------------------
        # Device
        # ----------------------------------------------------

        if device is None:
            device = (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )

        self.device = torch.device(device)

        # ----------------------------------------------------
        # Load model checkpoint
        # ----------------------------------------------------

        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
        )

        self.model = build_model_from_checkpoint(checkpoint)

        self.model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        self.model.to(self.device)
        self.model.eval()

        # ----------------------------------------------------
        # Load scaler
        # ----------------------------------------------------

        scaler_data = np.load(
            self.scaler_path
        )

        self.scaler = FeatureScaler()

        self.scaler.mean = scaler_data["mean"]
        self.scaler.std = scaler_data["std"]

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    def predict(self, sensor_sequence: np.ndarray) -> np.ndarray:
        """
        Predict speed for one 100-sample sensor sequence.

        Parameters
        ----------
        sensor_sequence:
            NumPy array with shape (100, 9).

        Returns
        -------
        np.ndarray
            Predicted speed in km/h with shape (100,).
        """

        sensor_sequence = np.asarray(
            sensor_sequence,
            dtype=np.float32,
        )

        if sensor_sequence.shape != (100, 9):
            raise ValueError(
                "Expected sensor sequence shape "
                f"(100, 9), got {sensor_sequence.shape}"
            )

        # Handle invalid sensor values.
        sensor_sequence = np.nan_to_num(
            sensor_sequence,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        # Apply the SAME scaler used during training.
        scaled = self.scaler.transform(
            sensor_sequence[np.newaxis, ...]
        )

        x = torch.from_numpy(
            scaled
        ).float().to(self.device)

        # ----------------------------------------------------
        # Model inference
        # ----------------------------------------------------

        with torch.no_grad():

            prediction = self.model(x)

        prediction = prediction.squeeze(0).cpu().numpy()

        # Speed cannot physically be negative.
        prediction = np.maximum(
            prediction,
            0.0,
        )

        return prediction


def predict_speed(
    sensor_sequence: np.ndarray,
    model_path: str = str(DEFAULT_MODEL_PATH),
    scaler_path: str = str(DEFAULT_SCALER_PATH),
) -> np.ndarray:
    """
    Convenience function for one-shot speed prediction.
    """

    estimator = SpeedEstimator(
        model_path=model_path,
        scaler_path=scaler_path,
    )

    return estimator.predict(
        sensor_sequence
    )