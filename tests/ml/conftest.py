"""Shared helpers for the navigation-ML tests.

Synthetic IMU windows keep the tests hermetic while still exercising the
real artifact-loading, feature, and inference paths.
"""

from __future__ import annotations

import numpy as np
import pytest

WINDOW_SIZE = 100
SENSOR_COLUMNS = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"]


def synthetic_window(seed: int = 0, rows: int = WINDOW_SIZE, channels: int = 6) -> np.ndarray:
    rng = np.random.RandomState(seed)
    return rng.normal(0.0, 1.0, (1, rows, channels)).astype(np.float64)


def needs_artifact(path: str):
    import pathlib

    p = pathlib.Path(path)
    if p.is_absolute():
        exists = p.exists()
    else:
        exists = pathlib.Path(__file__).resolve().parents[2].joinpath(path).exists()
    return pytest.mark.skipif(
        not exists,
        reason=f"artifact missing: {path}",
    )