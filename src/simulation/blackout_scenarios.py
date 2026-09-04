"""Deterministic GNSS-blackout scenario records.

A scenario is the *specification* of one GNSS-denied experiment: which trip,
which outage duration, how many intervals, and with which seed the exact
interval placement was drawn. Generation is fully reproducible: for a fixed
global seed the same ``(trip, duration, index)`` always yields the same
intervals (the sub-seed derives from a stable hash of the inputs).

Infeasible combos are never silently dropped: they are returned with an
explicit ``status`` and ``reason`` (e.g. ``trip_too_short``) so callers can
report exactly what was skipped and why.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

from .gnss_blackout import BlackoutImpossibleError, plan_blackout_intervals

OK = "ok"


@dataclass(frozen=True)
class BlackoutScenario:
    """One GNSS-denied experiment: trip + outage spec + deterministic seed.

    ``status`` is ``ok`` when the outage is realizable, otherwise an explicit
    reason (``trip_too_short``, ``invalid_duration``, ...) with ``message``.
    """

    scenario_id: str
    trip_id: str
    duration_s: float
    n_intervals: int
    seed: int
    status: str
    message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    n_spanned_seconds: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _scenario_id(trip_id: str, duration_s: float, index: int) -> str:
    dur = f"{duration_s:g}"
    return f"{trip_id}__blk{dur}s_{index:02d}"


def _scenario_seed(global_seed: int, trip_id: str, duration_s: float, index: int) -> int:
    import hashlib

    key = f"{global_seed}|{trip_id}|{duration_s}|{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:4], "big")


def build_scenarios(
    trip_ids: List[str],
    durations_s: Optional[List[float]] = None,
    seed: int = 2024,
    n_scenarios_per_duration: int = 1,
    n_intervals: int = 1,
) -> List[BlackoutScenario]:
    """Build scenario records for every (trip, duration, scenario-index) combo.

    Deterministic for a fixed ``seed``: trips/durations are iterated in sorted
    order and each scenario carries its own seeded plan. Scenario records are
    pure specs - feasibility against real timestamps is checked later via
    :func:`plan_scenario_intervals`, which raises an explicit error for combos
    that cannot be realized.
    """
    durations = list(durations_s or [5, 10, 20, 30, 60, 120])
    scenarios: List[BlackoutScenario] = []
    for trip_id in sorted(trip_ids):
        for duration in durations:
            for i in range(int(n_scenarios_per_duration)):
                sid = _scenario_id(trip_id, duration, i)
                sub_seed = _scenario_seed(seed, trip_id, duration, i)
                scenarios.append(
                    BlackoutScenario(
                        scenario_id=sid,
                        trip_id=trip_id,
                        duration_s=float(duration),
                        n_intervals=int(n_intervals),
                        seed=sub_seed,
                        status=OK,
                    )
                )
    return scenarios


def plan_scenario_intervals(
    scenario: BlackoutScenario,
    timestamps: List[float],
    min_pre_s: float = 0.0,
    min_post_s: float = 0.0,
    min_gap_s: float = 0.0,
    allow_overlap: bool = False,
):
    """Plan outage windows for ``scenario`` over real timestamps.

    Returns a list of :class:`~src.simulation.gnss_blackout.BlackoutInterval`,
    or raises :class:`BlackoutImpossibleError` (subclass of ValueError) with an
    explicit reason when the outage cannot be realized on this trip.
    """
    return plan_blackout_intervals(
        timestamps,
        duration_s=scenario.duration_s,
        n_intervals=scenario.n_intervals,
        seed=scenario.seed,
        trip_id=scenario.trip_id,
        min_pre_s=min_pre_s,
        min_post_s=min_post_s,
        min_gap_s=min_gap_s,
        allow_overlap=allow_overlap,
    )