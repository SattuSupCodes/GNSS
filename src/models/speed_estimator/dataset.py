"""PyTorch dataset for sequence-based smartphone speed estimation."""

from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset


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

DEFAULT_TARGET_COLUMN = "speed_kmh"


class SpeedSequenceDataset(Dataset):
    """Load fixed-length sensor sequences for speed estimation."""

    def __init__(
        self,
        parquet_path: str,
        feature_columns: Optional[List[str]] = None,
        target_column: str = DEFAULT_TARGET_COLUMN,
    ):
        self.parquet_path = Path(parquet_path)

        if not self.parquet_path.exists():
            raise FileNotFoundError(
                f"Dataset file not found: {self.parquet_path}"
            )

        self.feature_columns = (
            feature_columns
            if feature_columns is not None
            else DEFAULT_FEATURE_COLUMNS
        )
        self.target_column = target_column

        # Read the generated sequence file.
        df = pd.read_parquet(self.parquet_path)

        # Check that the required columns exist.
        required = ["sequence_id"] + self.feature_columns + [self.target_column]
        missing = [column for column in required if column not in df.columns]

        if missing:
            raise ValueError(
                f"Missing required columns: {missing}"
            )

        # Keep sequences in their original order.
        self.sequences = []

        for sequence_id, group in df.groupby("sequence_id", sort=False):
            group = group.sort_values("sample_in_window")

            # We expect complete 100-sample windows.
            if len(group) != 100:
                continue

            x = group[self.feature_columns].apply(
                pd.to_numeric, errors="coerce"
            ).to_numpy(dtype=np.float32)

            y = pd.to_numeric(
                group[self.target_column], errors="coerce"
            ).to_numpy(dtype=np.float32)

            # True where the target speed exists.
            target_mask = np.isfinite(y)

            # Neural networks cannot work with NaN input values.
            # Missing sensor values are represented as zero for now.
            x = np.nan_to_num(
                x,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )

            # Replace missing targets with zero, but keep the mask so
            # training/evaluation can ignore those positions.
            y = np.nan_to_num(
                y,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )

            self.sequences.append(
                (
                    torch.from_numpy(x),
                    torch.from_numpy(y),
                    torch.from_numpy(target_mask),
                )
            )

    def __len__(self) -> int:
        """Return the number of complete sequences."""
        return len(self.sequences)

    def __getitem__(self, index: int):
        """Return one sequence of sensors, speeds, and target-validity mask."""
        return self.sequences[index]