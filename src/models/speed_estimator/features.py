"""Feature preprocessing for smartphone speed estimation."""

from typing import List

import numpy as np


DEFAULT_FEATURE_COLUMNS = [
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


class FeatureScaler:
    """Standardize sensor features using statistics from training data."""

    def __init__(self, feature_columns: List[str] = None):
        if feature_columns is None:
            feature_columns = DEFAULT_FEATURE_COLUMNS

        self.feature_columns = feature_columns

        self.mean = None
        self.std = None

    def fit(self, x: np.ndarray):
        """Calculate mean and standard deviation from training data."""

        self.mean = np.mean(x, axis=(0, 1))
        self.std = np.std(x, axis=(0, 1))

        # Avoid division by zero for a feature with no variation.
        self.std = np.where(self.std < 1e-8, 1.0, self.std)

        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        """Standardize features using previously calculated statistics."""

        if self.mean is None or self.std is None:
            raise RuntimeError(
                "FeatureScaler must be fitted before transform()."
            )

        return (x - self.mean) / self.std

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        """Fit the scaler and then transform the data."""

        self.fit(x)
        return self.transform(x)