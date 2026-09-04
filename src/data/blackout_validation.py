"""Data-quality validation for Phase 3 blackout datasets.

Two entry points:

* :func:`validate_trip_frame` - sanity-checks a calibrated trip BEFORE blackout
  (timestamps, IMU/sensor availability, calibration columns, GNSS availability,
  trip ids, split assignments).
* :func:`validate_blackout_frame` - checks the hard invariants of a realized
  blackout dataset AFTER creation (masked GNSS is NaN only inside outages, every
  other column is byte-identical to the source, phases/availability agree, no
  rows deleted, intervals disjoint).

Every check produces a report entry; problems are reported, never silently
"fixed".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..simulation.gnss_blackout import GNSS_FIELDS

PHASES = {"pre_blackout", "blackout", "inter_blackout", "post_blackout"}

SENSOR_COLUMN_PREFIXES = (
    "accel_",
    "gyro_",
    "mag_",
    "gravity_",
    "orientation_",
    "orient_",
    "gravity_est_",
    "linear_accel_",
)

CALIBRATION_COLUMNS = [
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


@dataclass
class ValidationIssue:
    check: str
    status: str  # "ok" | "fail" | "warn"
    message: str


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    def add(self, check: str, status: str, message: str) -> None:
        self.issues.append(ValidationIssue(check=check, status=status, message=message))

    @property
    def failures(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.status == "fail"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.status == "warn"]

    @property
    def ok(self) -> bool:
        return not self.failures

    def assert_ok(self, reason: str = "validation failed") -> None:
        if not self.ok:
            raise AssertionError(f"{reason}:\n{self.summary()}")

    def summary(self) -> str:
        lines = []
        for issue in self.issues:
            lines.append(f"[{issue.status.upper():4}] {issue.check}: {issue.message}")
        if not self.issues:
            lines.append("No checks performed.")
        lines.append(
            f"-> {len(self.failures)} failures, {len(self.warnings)} warnings, "
            f"{len(self.issues)} checks total."
        )
        return "\n".join(lines)


def _eq_exact(a: np.ndarray, b: np.ndarray) -> bool:
    """Column equality that is exact (no tolerance) and NaN/NaT-aware."""
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape:
        return False
    if a.size == 0:
        return True
    a_num = np.issubdtype(a.dtype, np.number)
    b_num = np.issubdtype(b.dtype, np.number)
    if a_num and b_num:
        a = a.astype(float)
        b = b.astype(float)
        return bool(
            (np.isnan(a) == np.isnan(b)).all()
            and np.allclose(np.nan_to_num(a), np.nan_to_num(b), rtol=0.0, atol=0.0)
        )
    both_missing = pd.isna(a) | pd.isna(b)
    return bool(((a == b) | both_missing).all())


def validate_trip_frame(
    df: pd.DataFrame,
    *,
    calibration_columns: Optional[Sequence[str]] = None,
    split_assignments: Optional[Dict[str, str]] = None,
    min_sensor_availability: float = 0.5,
) -> ValidationReport:
    """Sanity-check a calibrated trip frame (run BEFORE blackout)."""
    report = ValidationReport()
    n = len(df)
    report.add("rows", "ok", f"{n} rows") if n else report.add(
        "rows", "fail", "empty frame"
    )
    if n == 0:
        return report

    # Timestamps.
    ts = pd.to_numeric(df["timestamp"], errors="coerce").to_numpy()
    if np.isnan(ts).any():
        report.add("timestamp_nan", "fail", f"{np.isnan(ts).sum()} NaN timestamps")
    elif np.diff(ts).min() < 0:
        report.add("timestamp_monotonic", "fail", "timestamps not monotonic")
    else:
        report.add("timestamp_monotonic", "ok", "timestamps monotonic non-decreasing")
    n_dup = int((np.diff(ts) == 0).sum())
    if n_dup:
        report.add("timestamp_duplicates", "fail", f"{n_dup} duplicate timestamps")
    else:
        report.add("timestamp_duplicates", "ok", "no duplicate timestamps")

    # IMU-derived sensor availability.
    sensor_cols = [c for c in df.columns if c.startswith(SENSOR_COLUMN_PREFIXES)]
    present = [c for c in sensor_cols if c in df.columns]
    missing = [c for c in ("accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z") if c not in df.columns]
    if missing:
        report.add("sensor_columns", "fail", f"missing canonical sensors {missing}")
    elif present:
        frac = min(df[c].notna().mean() for c in present)
        status = "ok" if frac >= min_sensor_availability else "warn"
        report.add(
            "sensor_availability", status,
            f"min non-NaN across {len(present)} sensor cols = {frac:.3f}",
        )
    else:
        report.add("sensor_columns", "warn", "no sensor columns found")

    # Phase 2 calibration columns.
    cal_cols = [c for c in (calibration_columns or CALIBRATION_COLUMNS) if c in df.columns]
    missing_cal = [c for c in (calibration_columns or CALIBRATION_COLUMNS) if c not in df.columns]
    if missing_cal:
        report.add(
            "calibration_columns", "warn",
            f"missing calibrated cols {missing_cal} (pre-pipeline source ok)",
        )
    elif cal_cols:
        nonnan = df[cal_cols].notna().any(axis=1).mean()
        report.add(
            "calibration_columns", "ok" if nonnan >= min_sensor_availability else "warn",
            f"{len(cal_cols)} calibrated cols present; {nonnan:.3f} rows fully populated",
        )

    # GNSS availability (forward-filled canonical data should be dense).
    gnss_cols = [c for c in GNSS_FIELDS if c in df.columns]
    if gnss_cols:
        av = df[gnss_cols].notna().any(axis=1).mean()
        report.add(
            "gnss_availability", "ok" if av >= min_sensor_availability else "warn",
            f"GNSS present on {av:.3f} of rows ({len(gnss_cols)} cols)",
        )
    else:
        report.add("gnss_availability", "warn", "no GNSS columns")

    # Trip id.
    if "trip_id" in df.columns:
        ids = df["trip_id"].dropna().unique()
        report.add(
            "trip_id", "ok" if len(ids) == 1 else "fail",
            f"trip_id={list(ids)[:3]}"
            if len(ids) == 1
            else f"{len(ids)} distinct trip ids",
        )
    else:
        report.add("trip_id", "warn", "no trip_id column")

    # Split membership.
    if split_assignments:
        trip_id = str(df["trip_id"].iloc[0]) if "trip_id" in df.columns else "?"
        split = split_assignments.get(trip_id)
        report.add(
            "split_assignment", "ok" if split else "warn",
            f"trip {trip_id} in split '{split}'" if split else f"trip {trip_id} not in splits",
        )
    return report


def validate_blackout_frame(
    source: pd.DataFrame,
    blackout: pd.DataFrame,
    *,
    mask_columns: Optional[Sequence[str]] = None,
    availability_column: str = "gnss_available",
    phase_column: str = "blackout_phase",
    blackout_id_column: str = "blackout_id",
    allow_overlap: bool = False,
    min_trip_duration_s: Optional[float] = None,
) -> ValidationReport:
    """Check the invariants a blackout dataset must satisfy.

    ``source`` is the pre-blackout frame; ``blackout`` its masked output. Every
    masked GNSS cell must be NaN exactly where ``availability_column`` is False;
    every other value must be identical to ``source``. Never mutates either
    frame and never "fixes" anything.
    """
    masks = [c for c in (mask_columns or GNSS_FIELDS) if c in blackout.columns]
    report = ValidationReport()

    if len(blackout) != len(source):
        report.add("rows", "fail",
                   f"row count changed {len(source)} -> {len(blackout)}")
    else:
        report.add("rows", "ok", f"{len(blackout)} rows preserved")

    if len(blackout) == 0:
        return report

    bt = pd.to_numeric(blackout["timestamp"], errors="coerce").to_numpy()
    st = pd.to_numeric(source["timestamp"], errors="coerce").to_numpy()
    if not np.array_equal(bt, st, equal_nan=True) or np.isnan(bt).any():
        report.add("timestamp", "fail", "timestamps altered by blackout")
    else:
        report.add("timestamp", "ok", "timestamps untouched")

    if np.diff(bt).min() < 0:
        report.add("timestamp_monotonic", "fail", "timestamps not monotonic")
    n_dup = int((np.diff(bt) == 0).sum())
    if np.diff(bt).min() < 0 or n_dup:
        report.add("timestamp_duplicates", "fail", f"{n_dup} duplicate timestamps")

    # Availability/phase consistency.
    if availability_column not in blackout.columns:
        report.add("gnss_available", "fail", f"missing column {availability_column}")
    else:
        av = blackout[availability_column].astype(bool).to_numpy()
        n_masked = int((~av).sum())
        report.add("gnss_available", "ok", f"GNSS available on {av.sum()}/{len(av)} rows; blackout masks {n_masked}")

    if phase_column in blackout.columns:
        phases = blackout[phase_column].astype(str)
        unknown = set(phases) - PHASES
        if unknown:
            report.add("phase_values", "fail", f"unknown phases {sorted(unknown)}")
        else:
            report.add("phase_values", "ok", f"phases {sorted(set(phases))}")
    # Masked rows must be flagged blackout; blackout rows must be masked.
    if availability_column in blackout.columns and phase_column in blackout.columns:
        masked = ~blackout[availability_column].astype(bool).to_numpy()
        is_bo = (blackout[phase_column].astype(str) == "blackout").to_numpy()
        mismatch = int((masked != is_bo).sum())
        report.add(
            "availability_phase", "ok" if mismatch == 0 else "fail",
            f"{mismatch} rows where gnss_available disagrees with blackout_phase",
        )

    # Masked columns: NaN inside, unchanged outside.
    if availability_column in blackout.columns:
        av = blackout[availability_column].astype(bool).to_numpy()
        n_ref = min(len(av), len(source))
        for c in masks:
            dst = blackout[c].to_numpy()[:n_ref]
            has_c = c in source.columns
            src = source[c].to_numpy()[:n_ref] if has_c else None
            inside_mask = ~av[:n_ref]
            inside_nan = (
                bool(np.isnan(dst[inside_mask]).all()) if inside_mask.any() else True
            )
            outside_same = (
                bool(_eq_exact(dst[av[:n_ref]], src[av[:n_ref]]))
                if (has_c and av[:n_ref].any())
                else True
            )
            report.add(
                f"gnss_field::{c}",
                "ok" if (inside_nan and outside_same) else "fail",
                "NaN inside + identical outside"
                if (inside_nan and outside_same)
                else f"inside_nan={inside_nan}, outside_identical={outside_same}",
            )

    # Everything else must be byte-identical to the source.
    shared = [
        c for c in blackout.columns
        if c in source.columns
        and c not in masks
        and c not in (availability_column, phase_column, blackout_id_column)
    ]
    diff_cols = [
        c for c in shared
        if not _eq_exact(source[c].to_numpy()[:n_common], blackout[c].to_numpy()[:n_common])
    ] if (n_common := min(len(source), len(blackout))) else []
    if diff_cols:
        report.add("preserved_columns", "fail", f"modified columns {diff_cols[:10]}")
    else:
        report.add("preserved_columns", "ok", f"{len(shared)} columns identical to source")

    # Intervals: disjointness + within bounds when info present.
    if blackout_id_column in blackout.columns:
        ids = pd.to_numeric(blackout[blackout_id_column], errors="coerce").dropna().unique()
        bounds = []
        for iv in sorted(ids):
            rows = pd.to_numeric(blackout[blackout_id_column], errors="coerce").to_numpy() == iv
            ts_in = bt[rows]
            if len(ts_in):
                bounds.append((float(ts_in.min()), float(ts_in.max())))
        overlap = False
        for (a0, a1), (b0, b1) in zip(bounds, bounds[1:]):
            if min(a1, b1) >= max(a0, b0) and (a1 > b0):
                overlap = True
        ok_overlap = (not overlap) or allow_overlap
        report.add(
            "interval_overlap",
            "ok" if ok_overlap else "fail",
            f"{len(bounds)} intervals; overlap detected" if overlap and not allow_overlap
            else f"{len(bounds)} disjoint intervals",
        )
        if bounds and min_trip_duration_s is not None:
            span = bt[-1] - bt[0]
            report.add(
                "trip_duration", "ok" if span >= min_trip_duration_s else "warn",
                f"trip spans {span:.1f}s (min {min_trip_duration_s:.1f}s)",
            )
    return report