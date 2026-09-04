"""End-to-end preprocessing pipeline for one canonical trip frame.

Chain (deterministic, order matters):

1. clean     : drop NaNs (IMU), dedupe timestamps, sort, clamp GNSS ranges
2. outlier   : flag/remove IMU spikes and GNSS jumps
3. filter    : low-pass IMU channels (default Butterworth 4 Hz @ 10 Hz)
4. resample  : uniform time grid at configured rate
5. normalize : z-score IMU channels (params fitted on the same frame)
6. coords    : add local ENU position columns from GNSS
7. sync      : forward-fill GNSS so every row carries the best-known fix

The pipeline is deterministic (fixed seed), takes a canonical DataFrame in and
returns an enriched canonical DataFrame out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..data.data_schema import (
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    GNSS_LAT,
    GNSS_LON,
    MAG_X,
    MAG_Y,
    MAG_Z,
    GRAV_X,
    GRAV_Y,
    GRAV_Z,
    TS_SEC,
)
from ..preprocessing import cleaning, coordinate_transforms, filtering, normalization, resampling, synchronization, outlier_detection


@dataclass
class PipelineConfig:
    """Knobs for the preprocessing pipeline."""

    fs: float = 10.0
    drop_na: bool = True
    dedupe: bool = True
    clamp_gnss: bool = True
    imu_spike_window: int = 15
    imu_spike_sigma: float = 8.0
    gnss_jump_kmh: float = 360.0
    lowpass_cutoff_hz: Optional[float] = 4.0
    filter_order: int = 4
    apply_zscore: bool = True
    add_enu: bool = True
    ffill_gnss: bool = True
    save_stats: bool = False
    metadata: Dict[str, object] = field(default_factory=dict)


def build_pipeline(config: Optional[PipelineConfig] = None) -> "PreprocessingPipeline":
    return PreprocessingPipeline(config or PipelineConfig())


class PreprocessingPipeline:
    """Applies the full chain to a canonical trip frame."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg = self.config
        out = df.copy()

        # 1. cleaning
        out = cleaning.clean_trip(
            out,
            drop_na=cfg.drop_na,
            dedupe=cfg.dedupe,
            sort_by_time=True,
            clamp=cfg.clamp_gnss,
        )

        # 2. outlier handling
        out = outlier_detection.remove_imu_spikes(
            out, window=cfg.imu_spike_window, threshold_sigma=cfg.imu_spike_sigma
        )
        out = outlier_detection.drop_gnss_jumps(out, max_speed_kmh=cfg.gnss_jump_kmh)

        # 3. low-pass filtering
        if cfg.lowpass_cutoff_hz is not None and len(out):
            out = filtering.butter_lowpass(
                out,
                columns=[
                    ACCEL_X, ACCEL_Y, ACCEL_Z,
                    GYRO_X, GYRO_Y, GYRO_Z,
                    MAG_X, MAG_Y, MAG_Z,
                    GRAV_X, GRAV_Y, GRAV_Z,
                ],
                cutoff_hz=cfg.lowpass_cutoff_hz,
                fs=cfg.fs,
                order=cfg.filter_order,
            )

        # 4. resampling to uniform grid (fills the spike NaNs via linear interp)
        if len(out):
            out = resampling.resample_uniform(out, fs=cfg.fs)

        # 5. normalization (fit on same frame; v1 keeps it simple)
        if cfg.apply_zscore and len(out):
            out = normalization.zscore(
                out,
                columns=[
                    ACCEL_X, ACCEL_Y, ACCEL_Z,
                    GYRO_X, GYRO_Y, GYRO_Z,
                    MAG_X, MAG_Y, MAG_Z,
                    GRAV_X, GRAV_Y, GRAV_Z,
                ],
            )

        # 6. local ENU coords
        if cfg.add_enu and len(out):
            out = coordinate_transforms.add_local_enu_columns(out)

        # 7. forward-fill GNSS
        if cfg.ffill_gnss and len(out):
            out = synchronization.ffill_gnss(out)

        return out.reset_index(drop=True)