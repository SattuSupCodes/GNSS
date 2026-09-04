"""Shared pytest configuration.

Adds the repository root to ``sys.path`` so ``src.*`` is importable from any
test module regardless of how pytest is invoked, and provides a synthetic,
canonical-smartphone trip fixture used across data/preprocessing tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[0]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def canonical_trip() -> pd.DataFrame:
    """A small, fully-canonical smartphone trip frame (10 Hz, ~12 s).

    Synthetic only - generated in code, never read from the real dataset.
    """
    n = 121
    ts = 1600000000.0 + np.arange(n) / 10.0
    rng = np.random.default_rng(7)
    data = {
        "timestamp": ts,
        "datetime": pd.to_datetime(ts, unit="s"),
        "time_since_start_ms": np.arange(n) * 100.0,
        "accel_x": rng.normal(0.1, 0.3, n),
        "accel_y": rng.normal(0.0, 0.3, n),
        "accel_z": rng.normal(9.8, 0.3, n),
        "gyro_x": rng.normal(0.0, 0.01, n),
        "gyro_y": rng.normal(0.0, 0.01, n),
        "gyro_z": rng.normal(0.0, 0.01, n),
        "mag_x": rng.normal(0.0, 2.0, n),
        "mag_y": rng.normal(0.0, 2.0, n),
        "mag_z": rng.normal(0.0, 2.0, n),
        "gravity_x": np.zeros(n),
        "gravity_y": np.zeros(n),
        "gravity_z": np.full(n, 9.8),
        "orientation_azimuth_deg": np.zeros(n),
        "orientation_pitch_deg": np.zeros(n),
        "orientation_roll_deg": np.zeros(n),
        # sparse GNSS: a fix every ~2 s
        "latitude_deg": np.where(np.arange(n) % 20 == 0, 52.5, np.nan),
        "longitude_deg": np.where(np.arange(n) % 20 == 0, -1.9, np.nan),
        "altitude_m": np.where(np.arange(n) % 20 == 0, 90.0, np.nan),
        "speed_kmh": np.where(np.arange(n) % 20 == 0, 40.0, np.nan),
        "position_accuracy_m": np.where(np.arange(n) % 20 == 0, 3.0, np.nan),
        "gps_heading_deg": np.where(np.arange(n) % 20 == 0, 90.0, np.nan),
        "gps_satellites": np.where(np.arange(n) % 20 == 0, 12.0, np.nan),
        "trip_id": np.full(n, "vw_test"),
        "source_file": np.full(n, "synthetic.csv"),
        "sync_status": np.full(n, "synchronised"),
    }
    return pd.DataFrame(data)