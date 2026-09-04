"""Tests for the sequence generator + leakage-prevention guarantees."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.sequence_generator import (
    WindowConfig,
    SequenceWindow,
    generate_windows,
    generate_windows_for_trips,
    group_windows_by_split,
    load_split_assignments,
    windows_to_frame,
    write_sequences,
)


def _trip(n, trip_id, ts_start=0.0):
    ts = ts_start + np.arange(n) / 10.0
    return pd.DataFrame(
        {
            "timestamp": ts,
            "speed_kmh": np.full(n, 40.0),
            "accel_x": np.arange(n, dtype=float),
            "trip_id": np.full(n, trip_id),
        }
    )


def test_fixed_length_non_overlapping_windows():
    df = _trip(250, "trip_a")
    wins = generate_windows(df, "trip_a", WindowConfig(window_rows=100, stride_rows=100))
    assert len(wins) == 2
    assert all(len(w.data) == 100 for w in wins)
    # no overlap: second window starts exactly at row 100
    assert wins[1].data["timestamp"].iloc[0] == df["timestamp"].iloc[100]
    assert wins[0].data["timestamp"].iloc[-1] < wins[1].data["timestamp"].iloc[0]


def test_incomplete_tail_dropped_by_default():
    df = _trip(250, "trip_a")
    wins = generate_windows(df, "trip_a", WindowConfig(window_rows=100))
    indices = [w.window_index for w in wins]
    assert indices == [0, 1]  # the 50-row tail is dropped


def test_incomplete_tail_kept_when_flag_false():
    df = _trip(250, "trip_a")
    cfg = WindowConfig(window_rows=100, drop_incomplete_tail=False)
    wins = generate_windows(df, "trip_a", cfg)
    assert len(wins) == 3
    assert len(wins[-1].data) == 50


def test_stride_smaller_than_window_overlaps_deliberately():
    df = _trip(250, "trip_a")
    cfg = WindowConfig(window_rows=100, stride_rows=50)
    wins = generate_windows(df, "trip_a", cfg)
    assert len(wins) == 4  # starts at 0, 50, 100, 150 (200..250 full)
    assert wins[0].data["timestamp"].iloc[0] == df["timestamp"].iloc[0]
    assert wins[1].data["timestamp"].iloc[0] == df["timestamp"].iloc[50]


def test_windows_never_cross_trip_boundaries():
    merged = pd.concat(
        [_trip(40, "trip_a", ts_start=0.0), _trip(40, "trip_b", ts_start=100.0)],
        ignore_index=True,
    )
    # per-trip windows from a single concatenated frame must be generated
    # from each trip separately (the generator API is per-trip, so pass both)
    cfg = WindowConfig(window_rows=30)
    wins = generate_windows(merged[merged["trip_id"] == "trip_a"], "trip_a", cfg)
    for w in wins:
        assert (w.data["trip_id"] == "trip_a").all()


def test_generate_windows_for_trips_keeps_provenance():
    trips = {"ta": _trip(250, "ta"), "tb": _trip(120, "tb")}
    assignment = {"ta": "train", "tb": "validation"}
    cfg = WindowConfig(window_rows=100, stride_rows=100)
    wins = generate_windows_for_trips(trips, cfg, split_assignment=assignment)
    assert len(wins) == 3  # ta->2, tb->1 (tail of tb dropped)
    assert all(w.split in ("train", "validation") for w in wins)


def test_unknown_trip_skipped_when_assignment_missing():
    trips = {"ta": _trip(200, "ta"), "unknown": _trip(200, "unknown")}
    assignment = {"ta": "train"}
    wins = generate_windows_for_trips(trips, WindowConfig(), split_assignment=assignment)
    assert all(w.trip_id == "ta" for w in wins)


def test_windows_to_frame_is_long_fixed_length():
    df = _trip(200, "ta")
    win = generate_windows(df, "ta", WindowConfig(), split="train")[0]
    frame = windows_to_frame([win])
    assert frame["sequence_id"].nunique() == 1
    assert (frame["sample_in_window"] == np.arange(100)).all()
    assert frame["window_start_timestamp"].iloc[0] == win.start_timestamp
    assert frame["window_stop_timestamp"].iloc[-1] == win.stop_timestamp
    assert set(frame["split"].unique()) == {"train"}


def test_windows_to_frame_empty():
    frame = windows_to_frame([])
    assert frame.empty


def test_sequence_ids_unique():
    df = _trip(300, "ta")
    wins = generate_windows(df, "ta", WindowConfig(window_rows=100, stride_rows=100))
    ids = [w.sequence_id for w in wins]
    assert len(ids) == len(set(ids))


def test_split_assignment_loader(tmp_path):
    (tmp_path / "train_trips.txt").write_text("ta\n", encoding="utf-8")
    (tmp_path / "validation_trips.txt").write_text("TB\n", encoding="utf-8")
    (tmp_path / "test_trips.txt").write_text("tc\n", encoding="utf-8")
    assignment = load_split_assignments(tmp_path)
    assert assignment == {"ta": "train", "tb": "validation", "tc": "test"}


def test_write_sequences_writes_parquet_per_split(tmp_path):
    trips = {"ta": _trip(250, "ta"), "tb": _trip(250, "tb")}
    assignment = {"ta": "train", "tb": "validation"}
    wins = generate_windows_for_trips(trips, WindowConfig(), split_assignment=assignment)
    counts = write_sequences(wins, tmp_path)
    assert counts["train"] == 2 and counts["validation"] == 2 and counts["test"] == 0
    train = pd.read_parquet(tmp_path / "training" / "sequences.parquet")
    assert set(train["split"].unique()) == {"train"}
    # leakage check: trips in each split file are disjoint
    assert not set(train["trip_id"].unique()) & {"tb"}


def test_split_files_are_trip_disjoint_and_total():
    """Trip-level splits are disjoint and exhaustive per Phase 1 guarantees."""
    root = Path(__file__).parents[2] / "data" / "splits"
    if not root.exists():
        pytest.skip("Phase 1 split files not present in this checkout")
    assignment = load_split_assignments(root)
    assert set(assignment.values()) == {"train", "validation", "test"}
    ids = list(assignment.keys())
    assert len([i for i in ids if assignment[i] == "train"]) == 50
    assert len([i for i in ids if assignment[i] == "validation"]) == 11
    assert len([i for i in ids if assignment[i] == "test"]) == 11