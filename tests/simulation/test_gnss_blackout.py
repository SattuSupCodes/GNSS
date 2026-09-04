"""Core simulator tests: masking, availability, phases, planning, seeds."""

from __future__ import annotations

import numpy as np
import pandas as np_pd
import pytest

from src.preprocessing.synchronization import ffill_gnss
from src.simulation.gnss_blackout import (
    GNSS_FIELDS,
    PHASE_BLACKOUT,
    PHASE_POST,
    PHASE_PRE,
    BlackoutImpossibleError,
    apply_blackout,
    plan_blackout_intervals,
)

FS = 10.0


def make_frame(n: int = 121, fs: float = FS, trip_id: str = "vw_test"):
    """Canonical-looking smartphone frame, GNSS forward-filled (like Phase 1)."""
    ts = 1600000000.0 + np.arange(n) / fs
    rng = np.random.default_rng(7)
    df = np_pd.DataFrame(
        {
            "timestamp": ts,
            "datetime": np_pd.to_datetime(ts, unit="s"),
            "time_since_start_ms": np.arange(n) * (1000.0 / fs),
            "accel_x": rng.normal(0.1, 0.3, n),
            "accel_y": rng.normal(0.0, 0.3, n),
            "accel_z": rng.normal(9.8, 0.3, n),
            "gyro_x": rng.normal(0.0, 0.01, n),
            "gyro_y": rng.normal(0.0, 0.01, n),
            "gyro_z": rng.normal(0.0, 0.01, n),
            "latitude_deg": np.where(np.arange(n) % 20 == 0, 52.5, np.nan),
            "longitude_deg": np.where(np.arange(n) % 20 == 0, -1.9, np.nan),
            "altitude_m": np.where(np.arange(n) % 20 == 0, 90.0, np.nan),
            "speed_kmh": np.where(np.arange(n) % 20 == 0, 40.0, np.nan),
            "position_accuracy_m": np.where(np.arange(n) % 20 == 0, 3.0, np.nan),
            "gps_heading_deg": np.where(np.arange(n) % 20 == 0, 90.0, np.nan),
            "gps_satellites": np.where(np.arange(n) % 20 == 0, 12.0, np.nan),
            "trip_id": np.array([trip_id] * n),
            "source_file": "synthetic.csv",
            "sync_status": "synchronised",
        }
    )
    return ffill_gnss(df)


@pytest.fixture
def frame():
    return make_frame()


def plan(df, duration_s=5.0, **kw):
    return plan_blackout_intervals(
        df["timestamp"], duration_s=duration_s,
        seed=kw.pop("seed", 2024), trip_id="vw_test", **kw,
    )


def test_masks_gnss_fields_inside_interval(frame):
    result = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0))
    out = result.frame
    masked = ~out["gnss_available"]
    assert masked.any()
    for col in GNSS_FIELDS:
        assert out.loc[masked, col].isna().all(), f"{col} not masked"


def test_imu_and_metadata_untouched(frame):
    result = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0))
    out = result.frame
    for col in ("accel_x", "accel_y", "accel_z", "gyro_x", "trip_id", "timestamp",
                "source_file", "sync_status"):
        assert np_pd.testing.assert_series_equal(
            out[col].reset_index(drop=True), frame[col].reset_index(drop=True)
        ) is None


def test_no_rows_deleted_or_added(frame):
    result = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0))
    assert len(result.frame) == len(frame)


def test_availability_and_phase_consistency(frame):
    out = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0)).frame
    masked = ~out["gnss_available"]
    assert (out.loc[masked, "blackout_phase"] == PHASE_BLACKOUT).all()
    assert (out.loc[out["gnss_available"], "blackout_phase"] != PHASE_BLACKOUT).all()
    assert set(out["blackout_phase"]) <= {PHASE_PRE, PHASE_BLACKOUT, PHASE_POST}


def test_real_duration_matches_timestamps(frame):
    result = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0))
    iv = result.intervals[0]
    assert abs((iv.masked_end_time - iv.masked_start_time) - 5.0) <= 2 * (1.0 / FS)


@pytest.mark.parametrize("duration_s", [5.0, 10.0, 30.0, 60.0, 120.0])
def test_longer_durations_mask_proportional_rows(duration_s):
    n = int((duration_s + 15.0) * FS)
    df = make_frame(n=n)
    result = apply_blackout(
        df, plan(df, duration_s, min_pre_s=5.0, min_post_s=5.0)
    )
    masked = result.total_masked_samples
    expected = duration_s * FS
    assert abs(masked - expected) <= 2 * FS, f"{masked} vs {expected}"


def test_multiple_intervals_disjoint_and_min_gap():
    df = make_frame(n=400)
    intervals = plan(
        df, 5.0, n_intervals=2, min_pre_s=5.0, min_post_s=5.0, min_gap_s=2.0
    )
    assert len(intervals) == 2
    gap = intervals[1].start_time - intervals[0].end_time
    assert gap >= 2.0 - 1e-9
    assert intervals[1].end_time <= df["timestamp"].iloc[-1] - 5.0 + 1e-9
    result = apply_blackout(df, intervals)
    ids = result.frame["blackout_id"].dropna().unique()
    assert set(ids) == {0.0, 1.0}


def test_invalid_duration_raises_explicit(frame):
    with pytest.raises(BlackoutImpossibleError) as exc:
        plan(frame, duration_s=50.0, min_pre_s=1.0, min_post_s=1.0)
    assert exc.value.reason == "trip_too_short"


def test_insufficient_pre_or_post_raises(frame):
    with pytest.raises(BlackoutImpossibleError):
        plan(frame, duration_s=5.0, min_pre_s=8.0, min_post_s=0.0)
    with pytest.raises(BlackoutImpossibleError):
        plan(frame, duration_s=5.0, min_pre_s=0.0, min_post_s=8.0)


def test_same_seed_deterministic(frame):
    a = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0, seed=42))
    b = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0, seed=42))
    np_pd.testing.assert_frame_equal(a.frame, b.frame)
    assert a.intervals[0].start_time == b.intervals[0].start_time


def test_different_seeds_give_different_intervals():
    df = make_frame(n=800)
    starts = {
        plan(df, 30.0, min_pre_s=10.0, min_post_s=10.0, seed=s)[0].start_time
        for s in (1, 2, 3)
    }
    assert len(starts) > 1


def test_interval_between_samples_masks_zero_rows():
    # Timestamps every 10 s; a 2 s window sits between fixes -> 0 masked rows.
    ts = 1600000000.0 + np.arange(0.0, 60.0, 10.0)
    sparse = np_pd.DataFrame({"timestamp": ts, "trip_id": "sparse"})
    intervals = plan_blackout_intervals(
        ts, duration_s=2.0, seed=5, min_pre_s=0.0, min_post_s=0.0
    )
    result = apply_blackout(sparse, intervals)
    assert result.intervals[0].n_samples == 0
    assert result.frame["gnss_available"].all()


def test_end_time_minus_start_time_is_real_duration(frame):
    iv = plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0)[0]
    assert abs((iv.end_time - iv.start_time) - 5.0) < 1e-9


def test_phase_ordering_pre_blackout_post(frame):
    out = apply_blackout(frame, plan(frame, 5.0, min_pre_s=1.0, min_post_s=1.0)).frame
    ts = out["timestamp"].to_numpy()
    first_bk = ts[out["blackout_phase"] == PHASE_BLACKOUT].min()
    last_bk = ts[out["blackout_phase"] == PHASE_BLACKOUT].max()
    assert (out.loc[out["timestamp"] < first_bk, "blackout_phase"] == PHASE_PRE).all()
    assert (out.loc[out["timestamp"] > last_bk, "blackout_phase"] == PHASE_POST).all()