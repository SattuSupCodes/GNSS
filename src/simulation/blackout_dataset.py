"""Assemble a complete GNSS-denied dataset for one scenario.

Combines the core simulator (:func:`src.simulation.gnss_blackout.apply_blackout`)
with the offline vehicle reference trajectory and produces a
:class:`BlackoutDataset` that clearly separates

* **runtime inputs**  - what a dead-reckoning / fusion model receives: IMU,
  calibrated/aligned sensors, timestamps, and the (masked) GNSS stream plus the
  ``gnss_available`` / ``blackout_phase`` annotations;
* **offline reference**  - the synchronized vehicle trajectory
  (``reference_*`` columns) that evaluation uses to compute position error but
  which must NEVER be fed as an input at runtime.

Reference values are attached only when a synchronized vehicle-reference file
exists for the trip; otherwise ``reference_available`` is False everywhere and
no reference position is fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .blackout_scenarios import BlackoutScenario, plan_scenario_intervals
from .gnss_blackout import BlackoutResult, apply_blackout

REFERENCE_PREFIX = "reference_"


def _match_reference_column(reference_df: pd.DataFrame, vehicle_column: str) -> Optional[str]:
    """Find the vehicle column, tolerant of the leading-space raw headers."""
    target = vehicle_column.strip().lower()
    for col in reference_df.columns:
        if col.strip().lower() == target:
            return col
    return None


def _attach_vehicle_reference(
    frame: pd.DataFrame,
    reference_df: pd.DataFrame,
    columns: Dict[str, str],
    available_column: str,
    source_column: str,
) -> pd.DataFrame:
    """Interpolate vehicle trajectory onto the smartphone grid (reference cols).

    Only interpolates INSIDE the reference time coverage; outside it the
    reference columns stay NaN and ``reference_available`` is False, so no
    trajectory is extrapolated/fabricated.
    """
    out = frame.copy()
    if reference_df is None or len(reference_df) == 0:
        for canonical_col in columns:
            out[canonical_col] = np.nan
        out[available_column] = False
        out[source_column] = "none"
        return out
    grid = pd.to_numeric(out["timestamp"], errors="coerce").to_numpy()
    ref_t = pd.to_numeric(reference_df["timestamp"], errors="coerce").to_numpy()
    finite_ref_t = np.isfinite(ref_t)

    coverage = np.zeros(len(grid), dtype=bool)
    for canonical_col, vehicle_col in columns.items():
        raw_col = _match_reference_column(reference_df, vehicle_col)
        if raw_col is None:
            out[canonical_col] = np.nan
            continue
        vals = pd.to_numeric(reference_df[raw_col], errors="coerce").to_numpy()
        finite = finite_ref_t & np.isfinite(vals)
        if not finite.any():
            out[canonical_col] = np.nan
            continue
        lo, hi = float(ref_t[finite].min()), float(ref_t[finite].max())
        interp = np.interp(grid, ref_t[finite], vals[finite])
        in_coverage = (grid >= lo) & (grid <= hi) & np.isfinite(grid)
        out[canonical_col] = np.where(in_coverage, interp, np.nan)
        coverage |= (in_coverage & np.isfinite(interp))

    out[available_column] = coverage
    out[source_column] = np.where(coverage, "vehicle", "none")
    return out


@dataclass
class BlackoutDataset:
    """One realized GNSS-denied dataset: masked frame + scenario + metadata."""

    frame: pd.DataFrame
    scenario: BlackoutScenario
    result: BlackoutResult
    source_file: Optional[str] = None
    reference_file: Optional[str] = None

    def runtime_frame(self) -> pd.DataFrame:
        """Frame of runtime inputs only: everything except ``reference_*``."""
        ref_cols = [c for c in self.frame.columns if c.startswith(REFERENCE_PREFIX)]
        return self.frame.drop(columns=ref_cols)

    def reference_frame(self) -> pd.DataFrame:
        """Frame of offline reference columns only (for evaluation)."""
        ref_cols = [c for c in self.frame.columns if c.startswith(REFERENCE_PREFIX)]
        cols = ["timestamp"] + ref_cols
        return self.frame[[c for c in cols if c in self.frame.columns]]

    @property
    def has_reference(self) -> bool:
        col = "reference_available"
        return col in self.frame.columns and bool(self.frame[col].any())

    def metadata(self) -> dict:
        """Serializable description of the dataset (scenario + realized mask)."""
        return {
            **self.scenario.to_dict(),
            "n_rows": int(len(self.frame)),
            "n_runtime_columns": int(len(self.runtime_frame().columns)),
            "n_reference_columns": int(len(self.reference_frame().columns) - 1),
            "has_reference": self.has_reference,
            "source_file": self.source_file,
            "reference_file": self.reference_file,
            "realization": self.result.to_dict(),
        }


def create_blackout_dataset(
    df: pd.DataFrame,
    scenario: BlackoutScenario,
    config,
    reference_df: Optional[pd.DataFrame] = None,
    source_file: Optional[str] = None,
) -> BlackoutDataset:
    """Run one scenario on one trip frame and attach offline reference.

    ``config`` is an :class:`src.simulation.config.BlackoutConfig`-shaped object
    providing ``mask_columns``, ``reference.*``, feasibility constraints and the
    availability/phase column names. Raises
    :class:`~src.simulation.gnss_blackout.BlackoutImpossibleError` with an
    explicit reason when the outage cannot fit the trip.
    """
    blackout_cfg = getattr(config, "blackout", config)
    timestamps = pd.to_numeric(df["timestamp"], errors="coerce").tolist()
    intervals = plan_scenario_intervals(
        scenario,
        timestamps,
        min_pre_s=float(getattr(blackout_cfg, "min_pre_blackout_s", 0.0)),
        min_post_s=float(getattr(blackout_cfg, "min_post_blackout_s", 0.0)),
        min_gap_s=float(getattr(blackout_cfg, "min_gap_between_blackouts_s", 0.0)),
        allow_overlap=bool(getattr(blackout_cfg, "allow_overlap", False)),
    )
    result = apply_blackout(
        df,
        intervals,
        mask_columns=list(getattr(blackout_cfg, "mask_columns", None) or []),
        availability_column=str(getattr(blackout_cfg, "availability_column", "gnss_available")),
        phase_column=str(getattr(blackout_cfg, "phase_column", "blackout_phase")),
        blackout_id_column=str(getattr(blackout_cfg, "blackout_id_column", "blackout_id")),
    )

    frame = result.frame
    reference_file: Optional[str] = None
    ref_cfg = getattr(config, "reference", None)
    if ref_cfg is not None and bool(getattr(ref_cfg, "attach_vehicle_reference", True)):
        frame = _attach_vehicle_reference(
            frame,
            reference_df if reference_df is not None else pd.DataFrame(),
            columns=dict(getattr(ref_cfg, "columns", {}) or {}),
            available_column=str(getattr(ref_cfg, "availability_column", "reference_available")),
            source_column=str(getattr(ref_cfg, "source_column", "reference_source")),
        )
        if reference_df is not None:
            reference_file = str(getattr(reference_df, "_source_path", "")) or None

    return BlackoutDataset(
        frame=frame,
        scenario=scenario,
        result=result,
        source_file=source_file,
        reference_file=reference_file,
    )