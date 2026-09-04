"""GNSS blackout simulation for GNSS-denied evaluation data.

Phase 3 core: given a canonical (calibrated/aligned) trip frame with real
timestamps and forward-filled GNSS, cut one or more outages where every GNSS
field is masked to NaN while IMU, calibrated/aligned sensors, timestamps, ids
and offline reference columns are left untouched.

Semantics
---------
* Durations are expressed in seconds over REAL timestamps. An outage is a time
  window ``[start_time, end_time]`` with ``end_time = start_time + duration``;
  every row whose timestamp falls in the window is masked. The actually spanned
  duration ``end_time - start_time`` is therefore derived from the data, never
  assumed from a nominal sample rate.
* Rows are never deleted. Values outside an outage are byte-identical to the
  input. ``gnss_available`` is False exactly on masked rows (the schema has no
  native availability field, so this column is the explicit convention).
* A blackout that cannot fit the trip (too short, insufficient pre/post GNSS,
  intervals too close when overlaps are disallowed) raises
  :class:`BlackoutImpossibleError` with an explicit reason instead of silently
  producing invalid data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# Canonical GNSS runtime fields masked during an outage. Mirrors
# src/preprocessing/synchronization.GNSS_COLS.
GNSS_FIELDS = [
    "latitude_deg",
    "longitude_deg",
    "altitude_m",
    "speed_kmh",
    "position_accuracy_m",
    "gps_heading_deg",
    "gps_satellites",
]

# Values marking one of four trajectory phases (relative to the outages).
PHASE_PRE = "pre_blackout"
PHASE_BLACKOUT = "blackout"
PHASE_INTER = "inter_blackout"  # between outages: GNSS available again
PHASE_POST = "post_blackout"


class BlackoutImpossibleError(ValueError):
    """A requested blackout cannot be realized on the given trip."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class BlackoutInterval:
    """One planned outage, expressed over real timestamps.

    ``requested_duration_s`` is the requested window width; ``masked_start_time``
    / ``masked_end_time`` are the first/last timestamps actually masked (real
    samples), so ``masked_end_time - masked_start_time`` is the real spanned
    duration and ``n_samples`` the number of rows affected.
    """

    index: int
    start_time: float
    end_time: float
    requested_duration_s: float
    masked_start_time: float
    masked_end_time: float
    n_samples: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BlackoutResult:
    """Outcome of :func:`apply_blackout`: the frame plus rich interval info."""

    frame: pd.DataFrame
    intervals: List[BlackoutInterval]
    availability_column: str = "gnss_available"
    phase_column: str = "blackout_phase"
    blackout_id_column: str = "blackout_id"

    @property
    def total_masked_samples(self) -> int:
        return sum(iv.n_samples for iv in self.intervals)

    def to_dict(self) -> dict:
        return {
            "n_rows": int(len(self.frame)),
            "n_intervals": len(self.intervals),
            "total_masked_samples": self.total_masked_samples,
            "intervals": [iv.to_dict() for iv in self.intervals],
            "availability_column": self.availability_column,
            "phase_column": self.phase_column,
            "blackout_id_column": self.blackout_id_column,
        }


def _sorted_numeric_timestamps(df: pd.DataFrame) -> np.ndarray:
    if "timestamp" not in df.columns:
        raise BlackoutImpossibleError("Frame has no 'timestamp' column.")
    t = pd.to_numeric(df["timestamp"], errors="coerce").to_numpy()
    finite = np.isfinite(t)
    if not finite.any():
        raise BlackoutImpossibleError("Frame has no finite timestamps.")
    return t[finite]


def _scenario_rng(seed: int, trip_id: str, duration_s: float, index: int) -> np.random.Generator:
    import hashlib

    key = f"{seed}|{trip_id}|{duration_s}|{index}".encode("utf-8")
    digest = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return np.random.default_rng(digest)


def plan_blackout_intervals(
    timestamps: Sequence[float],
    duration_s: float = 5.0,
    n_intervals: int = 1,
    seed: int = 2024,
    trip_id: str = "",
    index_base: int = 0,
    min_pre_s: float = 0.0,
    min_post_s: float = 0.0,
    min_gap_s: float = 0.0,
    allow_overlap: bool = False,
) -> List[BlackoutInterval]:
    """Plan outage windows over real timestamps (deterministic given ``seed``).

    Each interval is a ``[start, start + duration]`` window. Feasibility is
    checked on real span: ``t0 + min_pre`` must exist, and the last interval
    must end no later than ``t[-1] - min_post``. Returns planned intervals with
    placeholders (masked endpoints filled in by :func:`apply_blackout`).

    Raises :class:`BlackoutImpossibleError` with an explicit reason when the
    blackout cannot be realized.
    """
    t = np.asarray(timestamps, dtype=float)
    t = np.sort(t)
    if len(t) < 2:
        raise BlackoutImpossibleError(
            "trip_too_short", f"Trip has {len(t)} samples; need >= 2."
        )
    if duration_s <= 0:
        raise BlackoutImpossibleError(
            "invalid_duration", f"duration_s must be > 0, got {duration_s}."
        )
    if n_intervals < 1:
        raise BlackoutImpossibleError(
            "invalid_intervals", f"n_intervals must be >= 1, got {n_intervals}."
        )

    t0, t1 = float(t[0]), float(t[-1])
    span = t1 - t0
    required = (
        duration_s * n_intervals
        + (min_gap_s * (n_intervals - 1) if not allow_overlap else 0.0)
        + min_pre_s
        + min_post_s
    )
    if required > span:
        raise BlackoutImpossibleError(
            "trip_too_short",
            (
                f"Requested {n_intervals}x{duration_s:.1f}s blackout needs "
                f"{required:.1f}s of span but trip spans {span:.1f}s."
            ),
        )

    rng = _scenario_rng(seed, trip_id, duration_s, index_base)
    excess = span - required
    gaps = rng.dirichlet(np.ones(n_intervals + 1)) * excess

    intervals: List[BlackoutInterval] = []
    start = t0 + min_pre_s
    gap_spent = 0.0
    for i in range(n_intervals):
        start += gaps[i]
        w_start = float(start)
        w_end = float(start + duration_s)
        intervals.append(
            BlackoutInterval(
                index=index_base + i,
                start_time=w_start,
                end_time=w_end,
                requested_duration_s=float(duration_s),
                masked_start_time=float("nan"),
                masked_end_time=float("nan"),
                n_samples=0,
            )
        )
        start = start + duration_s
        if not allow_overlap and i < n_intervals - 1:
            start += min_gap_s

    return intervals


def apply_blackout(
    df: pd.DataFrame,
    intervals: Sequence[BlackoutInterval],
    mask_columns: Optional[Sequence[str]] = None,
    availability_column: str = "gnss_available",
    phase_column: str = "blackout_phase",
    blackout_id_column: str = "blackout_id",
) -> BlackoutResult:
    """Mask GNSS fields during the given outage windows.

    Returns a :class:`BlackoutResult` whose ``frame`` is a new DataFrame with:

    * GNSS columns from ``mask_columns`` set to NaN exactly inside the windows
      (columns not present in the frame are skipped);
    * ``gnss_available`` = False exactly on masked rows, True elsewhere;
    * ``blackout_phase`` in ``{pre_blackout, blackout, inter_blackout,
      post_blackout}``;
    * ``blackout_id`` = interval index on masked rows, NaN elsewhere.

    All other columns (IMU, calibrated/aligned sensors, timestamps, trip ids,
    metadata, reference fields) are copied unchanged. No rows are deleted.
    """
    cols = [c for c in (mask_columns or GNSS_FIELDS) if c in df.columns]
    out = df.copy()
    t = pd.to_numeric(out["timestamp"], errors="coerce").to_numpy()
    masked = np.zeros(len(out), dtype=bool)
    applied: List[BlackoutInterval] = []

    for iv in intervals:
        in_window = (t >= iv.start_time) & (t <= iv.end_time)
        ids = np.flatnonzero(in_window)
        masked |= in_window
        n = int(len(ids))
        if n == 0:
            # Window lands between samples (e.g. end_time before next fix).
            # Still record it; availability is unaffected by an empty window.
            m_start = m_end = float("nan")
        else:
            m_start = float(t[ids[0]])
            m_end = float(t[ids[-1]])
        applied.append(
            BlackoutInterval(
                index=iv.index,
                start_time=iv.start_time,
                end_time=iv.end_time,
                requested_duration_s=iv.requested_duration_s,
                masked_start_time=m_start,
                masked_end_time=m_end,
                n_samples=n,
            )
        )

    if masked.any():
        for c in cols:
            if c in out.columns:
                out.loc[masked, c] = np.nan

    id_values = np.full(len(out), np.nan)
    for iv in intervals:
        in_window = (t >= iv.start_time) & (t <= iv.end_time)
        id_values[in_window] = float(iv.index)
    out[blackout_id_column] = id_values

    out[availability_column] = ~masked

    phases = np.full(len(out), PHASE_PRE, dtype=object)
    if intervals:
        phases = np.where(masked, PHASE_BLACKOUT, PHASE_PRE).astype(object)
        for i in range(len(intervals) - 1):
            between = (
                (t > intervals[i].end_time) & (t < intervals[i + 1].start_time)
            ) & ~masked
            phases[between] = PHASE_INTER
        phases[t > intervals[-1].end_time] = PHASE_POST
    out[phase_column] = phases

    return BlackoutResult(
        frame=out,
        intervals=applied,
        availability_column=availability_column,
        phase_column=phase_column,
        blackout_id_column=blackout_id_column,
    )


def interval_status(span_s: float, duration_s: float) -> str:
    """Explicit reason why an outage is (im)possible for a given span."""
    if span_s < duration_s:
        return "trip_too_short"
    return "ok"