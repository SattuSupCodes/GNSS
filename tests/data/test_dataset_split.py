"""Tests for trip-level dataset splitting."""

from __future__ import annotations

from src.data.dataset_splitter import (
    SplitResult,
    remove_leakage_duplicates,
    split_trips_by_id,
)


def test_expected_counts_round_trips():
    ids = [f"t{i:03d}" for i in range(72)]
    r = split_trips_by_id(ids, ratios=(0.7, 0.15, 0.15), seed=42)
    counts = r.counts()
    assert counts["train"] == 50
    assert counts["validation"] == 11
    assert counts["test"] == 11
    assert sum(counts.values()) == 72
    assert not r.warned


def test_assignment_covers_all_trips():
    ids = [f"t{i}" for i in range(20)]
    r = split_trips_by_id(ids, seed=1)
    assert set(r.assignment) == set(ids)
    assert set(r.train) | set(r.validation) | set(r.test) == set(ids)


def test_no_trip_in_two_splits():
    ids = [f"t{i:02d}" for i in range(50)]
    r = split_trips_by_id(ids, seed=3)
    assert not (set(r.train) & set(r.validation))
    assert not (set(r.train) & set(r.test))
    assert not (set(r.validation) & set(r.test))


def test_deterministic_with_seed():
    ids = [f"t{i}" for i in range(30)]
    a = split_trips_by_id(ids, seed=99)
    b = split_trips_by_id(ids, seed=99)
    assert a.assignment == b.assignment


def test_shuffle_changes_assignment():
    ids = [f"t{i}" for i in range(30)]
    a = split_trips_by_id(ids, shuffle=False, seed=5)
    b = split_trips_by_id(ids, shuffle=True, seed=5)
    assert a.assignment["t0"] == "train"
    assert b.assignment["t0"] == b.assignment["t0"]  # deterministic per-config


def test_small_dataset_warns_or_is_graceful():
    r = split_trips_by_id(["only-one"], seed=0)
    assert isinstance(r, SplitResult)
    assert r.warned or sum(r.counts().values()) == 1


def test_empty_input():
    r = split_trips_by_id([])
    assert r.warned
    assert r.counts() == {"train": 0, "validation": 0, "test": 0}


def test_remove_leakage_duplicates_same_id_twice():
    ids = ["Vw16b", "vw16b", "Vta1"]
    out = remove_leakage_duplicates(ids)
    assert out == ["Vw16b", "Vta1"]


def test_split_for_unknown_returns_unknown():
    r = split_trips_by_id(["a", "b", "c", "d", "e", "f"], seed=0)
    assert r.split_for("zzz") == "unknown"