"""Calibration pipeline: canonical trip -> calibrated + aligned canonical trip.

Composes the calibration modules into one reproducible, config-driven pipeline:

    raw canonical trip (Phase 1 processed frame)
              |
    gravity estimation                 (gravity_est_* , linear_accel_*)
              |
    sensor calibration                 (accel/gyro/mag -> *_cal columns)
              |
    orientation estimation             (orient_* columns from accel+gyro+mag)
              |
    phone alignment                    (device -> world, *_aligned columns)
              |
    calibrated canonical trip

Guarantees
----------
* Raw Phase 1 columns are never modified or dropped; every new value lives in a
  distinct `_est` / `_cal` / `_aligned` / `orient_*` column.
* timestamps, trip ids, source files, sync status and GNSS values are preserved.
* category / driver are (re)derived from the source path when available.
* A serialisable metadata block records exactly what was estimated, configured
  or unavailable, and which alignment convention was applied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..data.data_schema import (
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    CATEGORY,
    DRIVER,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    MAG_X,
    MAG_Y,
    MAG_Z,
    SOURCE_FILE,
    SYNC_STATUS,
    TRIP_ID,
)
from ..data.io_vnbd_loader import _category_from_path, _driver_from_folder
from .gravity_estimation import GRAVITY_EST_COLUMNS, GravityEstimator
from .orientation_estimation import ORIENTATION_COLUMNS, OrientationEstimator
from .phone_alignment import (
    WORLD_FRAME,
    AlignmentConvention,
    PhoneAligner,
    get_preset,
)
from .sensor_calibration import (
    SensorCalibrationProfile,
    apply_calibration,
    configured_profile,
    estimate_gyro_bias,
    unavailable_profile,
)

CALIBRATED_COLUMN_PREFIXES = ("accel_", "gyro_", "mag_")
ALIGNED_SUFFIX = "_aligned"


@dataclass
class CalibrationConfig:
    """Config for the full calibration pipeline (mirrors config YAML)."""

    gravity_method: str = "lowpass"
    gravity_cutoff_hz: float = 0.05
    gravity_filter_order: int = 4
    fs: float = 10.0
    gravity_min_samples: int = 20

    fusion_gain: float = 0.1
    ema_tau_s: float = 1.0
    mag_field_min_ut: float = 20.0
    mag_field_max_ut: float = 70.0

    alignment_convention: str = "TOP_NORTH_SCREEN_UP"
    alignment_yaw_deg: Optional[float] = None
    alignment_pitch_deg: Optional[float] = None
    alignment_roll_deg: Optional[float] = None

    calibrate_accel: bool = False
    calibrate_gyro: bool = False
    calibrate_mag: bool = False
    estimate_gyro_bias_from_rest: bool = False

    def to_dict(self) -> Dict[str, object]:
        return {
            "gravity": {
                "method": self.gravity_method,
                "cutoff_hz": self.gravity_cutoff_hz,
                "filter_order": self.gravity_filter_order,
                "fs": self.fs,
                "min_samples": self.gravity_min_samples,
            },
            "orientation": {
                "fusion_gain": self.fusion_gain,
                "ema_tau_s": self.ema_tau_s,
                "mag_field_min_ut": self.mag_field_min_ut,
                "mag_field_max_ut": self.mag_field_max_ut,
            },
            "alignment": {
                "convention": self.alignment_convention,
                "yaw_deg": self.alignment_yaw_deg,
                "pitch_deg": self.alignment_pitch_deg,
                "roll_deg": self.alignment_roll_deg,
            },
            "calibration": {
                "accel": self.calibrate_accel,
                "gyro": self.calibrate_gyro,
                "mag": self.calibrate_mag,
                "estimate_gyro_bias_from_rest": self.estimate_gyro_bias_from_rest,
            },
        }


@dataclass
class CalibrationResult:
    """Output of :meth:`CalibrationPipeline.run`."""

    frame: pd.DataFrame
    metadata: Dict[str, object]
    added_columns: List[str]

    @property
    def status(self) -> str:
        return str(self.metadata.get("status", "unknown"))


class CalibrationPipeline:
    """Applies gravity/sensor/orientation/alignment to one canonical trip."""

    def __init__(self, config: Optional[CalibrationConfig] = None):
        self.config = config or CalibrationConfig()

    # ------------------------------------------------------------------ #

    def _build_alignment(self) -> AlignmentConvention:
        if (
            self.config.alignment_yaw_deg is not None
            or self.config.alignment_pitch_deg is not None
            or self.config.alignment_roll_deg is not None
        ):
            return AlignmentConvention(
                name="custom",
                yaw_deg=self.config.alignment_yaw_deg or 0.0,
                pitch_deg=self.config.alignment_pitch_deg or 0.0,
                roll_deg=self.config.alignment_roll_deg or 0.0,
                source="configured",
                description="Custom device->world Euler angles from calibration config.",
            )
        return get_preset(self.config.alignment_convention)

    # ------------------------------------------------------------------ #

    def run(
        self,
        df: pd.DataFrame,
        trip_id: Optional[str] = None,
        source_file: Optional[str] = None,
        gyro_rest_samples: Optional[np.ndarray] = None,
    ) -> CalibrationResult:
        cfg = self.config
        out = df.copy()
        added: List[str] = []

        # --- 1. gravity estimation ------------------------------------ #
        gravity_step = GravityEstimator(
            method=cfg.gravity_method,
            cutoff_hz=cfg.gravity_cutoff_hz,
            filter_order=cfg.gravity_filter_order,
            fs=cfg.fs,
            min_samples=cfg.gravity_min_samples,
        )
        grav_res = gravity_step.fit_transform(out)
        for c in GRAVITY_EST_COLUMNS:
            if c in grav_res.frame.columns:
                out[c] = grav_res.frame[c]
                added.append(c)

        # --- 2. sensor calibration ------------------------------------ #
        profiles: Dict[str, SensorCalibrationProfile] = {}
        profiles["accel"] = self._profile_for(
            "accel", cfg.calibrate_accel, ("accel_x", "accel_y", "accel_z")
        )
        profiles["mag"] = self._profile_for(
            "mag", cfg.calibrate_mag, ("mag_x", "mag_y", "mag_z")
        )
        if cfg.calibrate_gyro and gyro_rest_samples is not None:
            gyro_prof = estimate_gyro_bias(gyro_rest_samples, sensor="gyro")
            profiles["gyro"] = gyro_prof if gyro_prof.is_available() else self._profile_for(
                "gyro", False, ("gyro_x", "gyro_y", "gyro_z")
            )
        elif cfg.calibrate_gyro:
            # Rest estimation requested but no rest samples provided: keep an
            # honest configured-identity profile (never a pseudo "unavailable",
            # since we applied no correction at all).
            profiles["gyro"] = configured_profile(
                "gyro",
                note="Gyro rest-bias estimation requested but no rest samples "
                "were provided; no correction applied.",
            )
        else:
            profiles["gyro"] = self._profile_for(
                "gyro", cfg.calibrate_gyro, ("gyro_x", "gyro_y", "gyro_z")
            )
        for sensor, base in (
            ("accel", ["accel_x", "accel_y", "accel_z"]),
            ("gyro", ["gyro_x", "gyro_y", "gyro_z"]),
            ("mag", ["mag_x", "mag_y", "mag_z"]),
        ): # Some IO-VNBD trips do not contain every smartphone sensor.
    # Missing sensors must remain unavailable; never fabricate values.
            if not all(c in out.columns for c in base):
                continue

            pre = set(out.columns)
            out = apply_calibration(
                out,
                sensor,
                profiles[sensor],
                base_cols=base,
            )
            added += [c for c in out.columns.difference(pre)]

        # --- 3. orientation estimation -------------------------------- #
        orient = OrientationEstimator(
            fusion_gain=cfg.fusion_gain,
            ema_tau_s=cfg.ema_tau_s,
            mag_field=(cfg.mag_field_min_ut, cfg.mag_field_max_ut),
        )
        gyro_cols = (
            [c + "_cal" for c in ("gyro_x", "gyro_y", "gyro_z")]
            if all(c + "_cal" in out.columns for c in ("gyro_x", "gyro_y", "gyro_z"))
            else ["gyro_x", "gyro_y", "gyro_z"]
        )
        mag_base = (
            "mag_x", "mag_y", "mag_z"
        ) 
        if all(f"{c}_cal" in out.columns for c in mag_base):
            mag_cols = [f"{c}_cal" for c in mag_base]
        elif all(c in out.columns for c in mag_base):
            mag_cols = list(mag_base)
        else:
            mag_cols = None
        accel_cols = ["accel_x", "accel_y", "accel_z"]
        orient_res = orient.estimate(
            out,
            accel=accel_cols,
            gyro=gyro_cols,
            mag=mag_cols,
            gravity=["gravity_est_x", "gravity_est_y", "gravity_est_z"],
        )
        for c in ORIENTATION_COLUMNS:
            out[c] = orient_res.frame[c]
            added.append(c)

        # --- 4. phone alignment --------------------------------------- #
        convention = self._build_alignment()
        aligner = PhoneAligner(convention)
        aligned_from: List[str] = []
        for base in ("accel", "gyro", "mag"):
            cal_names = [
                f"{base}_x_cal",
                f"{base}_y_cal",
                f"{base}_z_cal",
            ]
            raw_names = [
                f"{base}_x",
                f"{base}_y",
                f"{base}_z",
            ]

            if all(c in out.columns for c in cal_names):
                src = cal_names
            elif all(c in out.columns for c in raw_names):
                src = raw_names
            else:
                # Sensor is genuinely unavailable for this trip.
                continue

            raw = np.column_stack(
                [
                    pd.to_numeric(out[c], errors="coerce").to_numpy()
                    for c in src
                ]
            )

            aligned = aligner.align_vectors(raw)

            for axis, comp in zip("xyz", range(3)):
                out[f"{base}_{axis}{ALIGNED_SUFFIX}"] = aligned[:, comp]
                added.append(f"{base}_{axis}{ALIGNED_SUFFIX}")

            aligned_from.extend(src)
        align_meta = aligner.metadata
        align_meta = dict(align_meta)
        align_meta["applied_to"] = aligned_from

        # --- 5. metadata / provenance ---------------------------------- #
        src = source_file or (
            str(out[SOURCE_FILE].iloc[0]) if SOURCE_FILE in out.columns and len(out) else None
        )
        tid = trip_id or (
            str(out[TRIP_ID].iloc[0]) if TRIP_ID in out.columns and len(out) else None
        )
        if src:
            if CATEGORY not in out.columns:
                cat = _category_from_path(Path(src))
                if cat:
                    out[CATEGORY] = cat
                    added.append(CATEGORY)
            if DRIVER not in out.columns:
                drv = _driver_from_folder(Path(src).parent)
                if drv:
                    out[DRIVER] = drv
                    added.append(DRIVER)

        metadata = self._build_metadata(
            out=out,
            trip_id=tid,
            source_file=src,
            gravity_status=grav_res.status,
            gravity_message=grav_res.message,
            orient_config=orient_res.config,
            align_meta=align_meta,
            profiles=profiles,
        )
        return CalibrationResult(frame=out, metadata=metadata, added_columns=added)

    # ------------------------------------------------------------------ #

    def _profile_for(
        self, sensor: str, enable: bool, base_cols: List[str]
    ) -> SensorCalibrationProfile:
        if not enable:
            return configured_profile(
                sensor,
                note="Configured identity calibration (no correction applied).",
            )
        return unavailable_profile(
            sensor, note="Estimation mode enabled but no fit data was provided in run()."
        )

    def _build_metadata(
        self,
        out: pd.DataFrame,
        trip_id: Optional[str],
        source_file: Optional[str],
        gravity_status: str,
        gravity_message: str,
        orient_config: Dict[str, object],
        align_meta: Dict[str, object],
        profiles: Dict[str, SensorCalibrationProfile],
    ) -> Dict[str, object]:
        avail: Dict[str, float] = {}
        for group, cols in (
            ("accel", ("accel_x", "accel_y", "accel_z")),
            ("gyro", ("gyro_x", "gyro_y", "gyro_z")),
            ("mag", ("mag_x", "mag_y", "mag_z")),
            ("gnss", ("latitude_deg", "longitude_deg")),
        ):
            present = [c for c in cols if c in out.columns]
            if present:
                sub = out[present].apply(pd.to_numeric, errors="coerce")
                avail[group] = float(sub.notna().all(axis=1).mean())
            else:
                avail[group] = 0.0
        status = "ok"
        per_sensor = {name: p.to_dict() for name, p in profiles.items()}
        return {
            "pipeline": "calibration",
            "version": 1,
            "trip_id": trip_id,
            "source_file": source_file,
            "sync_status": (
                str(out[SYNC_STATUS].iloc[0]) if SYNC_STATUS in out.columns and len(out) else None
            ),
            "frame_rows": int(len(out)),
            "config": cfg_to_dict(self.config),
            "gravity": {
                "status": gravity_status,
                "message": gravity_message,
                "magnitude_mean": float(np.nanmean(pd.to_numeric(out.get("gravity_est_magnitude"), errors="coerce")))
                if "gravity_est_magnitude" in out.columns
                else None,
            },
            "orientation": orient_config,
            "alignment": align_meta,
            "calibration": {"profiles": per_sensor, "status": status},
            "sensor_availability": avail,
            "status": status,
            "notes": [
                "Raw Phase 1 columns are preserved untouched.",
                "aligned columns = calibrated device-frame values rotated into " + WORLD_FRAME + ".",
            ],
        }


def cfg_to_dict(cfg: CalibrationConfig) -> Dict[str, object]:
    return cfg.to_dict()