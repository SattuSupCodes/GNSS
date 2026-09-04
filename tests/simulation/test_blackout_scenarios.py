"""Tests for deterministic blackout scenario records."""

from __future__ import annotations

import re
from unittest.mock import patch

import pandas as pd
import pytest

from src.simulation.blackout_scenarios import (
    BlackoutScenario,
    build_scenarios,
    plan_scenario_intervals,
)
from src.simulation.gnss_blackout import BlackoutImpossibleError

TRIPS = ["vw16b", "s1", "vta10"]


def ts_frame(span_s: float = 200.0):
    return pd.DataFrame({"timestamp": pd.Series([1000.0, 1000.0 + span_s])})


def test_scenarios_count_and_unique_file_safe_ids():
    scen = build_scenarios(
        TRIPS, durations_s=[5.0, 10.0], seed=2024, n_scenarios_per_duration=2
    )
    assert len(scen) == 3 * 2 * 2
    ids = [s.scenario_id for s in scen]
    assert len(set(ids)) == len(ids)
    for sid in ids:
        assert re.fullmatch(r"[A-Za-z0-9_.-]+", sid)


def test_deterministic_same_seed():
    a = build_scenarios(TRIPS, durations_s=[5.0, 10.0, 30.0], seed=42)
    b = build_scenarios(TRIPS, durations_s=[5.0, 10.0, 30.0], seed=42)
    assert a == b


def test_different_seed_changes_scenario_seeds():
    a = build_scenarios(TRIPS, durations_s=[5.0], seed=1)
    b = build_scenarios(TRIPS, durations_s=[5.0], seed=2)
    assert [s.seed for s in a] != [s.seed for s in b]


def test_scenario_records_are_pure_specs():
    scen = build_scenarios(["x"], durations_s=[5.0], seed=1)[0]
    assert isinstance(scen, BlackoutScenario)
    assert scen.status == "ok"
    d = scen.to_dict()
    assert d["scenario_id"] == "x__blk5s_00"
    assert d["trip_id"] == "x"
    assert d["duration_s"] == 5.0
    assert d["n_intervals"] == 1


def test_plan_feasible_intervals():
    scen = build_scenarios(["x"], durations_s=[30.0], seed=7)[0]
    intervals = plan_scenario_intervals(scen, ts_frame().timestamp.tolist())
    assert len(intervals) == 1
    assert abs(intervals[0].requested_duration_s - 30.0) < 1e-9


def test_plan_infeasible_raises_explicit_reason():
    scen = build_scenarios(["x"], durations_s=[120.0], seed=7)[0]
    with pytest.raises(BlackoutImpossibleError) as exc:
        plan_scenario_intervals(scen, ts_frame(span_s=50.0).timestamp.tolist())
    assert exc.value.reason == "trip_too_short"


def test_plan_deterministic_per_scenario():
    a = build_scenarios(["x"], durations_s=[10.0], seed=5)[0]
    b = build_scenarios(["x"], durations_s=[10.0], seed=5)[0]

    def norm(intervals):
        return [
            (iv.start_time, iv.end_time, iv.requested_duration_s) for iv in intervals
        ]

    assert norm(plan_scenario_intervals(a, ts_frame().timestamp.tolist())) == \
        norm(plan_scenario_intervals(b, ts_frame().timestamp.tolist()))


@patch("src.simulation.blackout_scenarios._scenario_seed")
def test_seed_derived_instead_of_global_hash(mock_seed):
    mock_seed.side_effect = lambda g, t, d, i: g + i
    build_scenarios(["x"], durations_s=[5.0], seed=9)
    mock_seed.assert_called()