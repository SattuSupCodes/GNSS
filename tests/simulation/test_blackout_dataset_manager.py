"""Integration: DatasetManager blackout-loading API on a tmp workspace."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.data.dataset_manager import DatasetManager
from src.simulation.blackout_dataset import create_blackout_dataset
from src.simulation.blackout_scenarios import build_scenarios
from src.simulation.config import EvaluationConfig


@pytest.fixture
def workspace(tmp_path):
    raw = tmp_path / "data" / "raw"
    processed = tmp_path / "data" / "processed"
    blackout = tmp_path / "data" / "blackout"
    raw.mkdir(parents=True)
    processed.mkdir(parents=True)
    blackout.mkdir(parents=True)
    return raw, processed, blackout


def _write_scenario(blackout_root, suffix_dir, scenario_id, frame):
    out = blackout_root / suffix_dir
    out.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out / f"{scenario_id}.parquet", index=False)
    (out / f"{scenario_id}_metadata.json").write_text(
        json.dumps({"scenario_id": scenario_id, "n_rows": len(frame)}), encoding="utf-8"
    )
    return out / f"{scenario_id}.parquet"


@pytest.fixture
def populated(workspace):
    raw, processed, blackout = workspace
    dm = DatasetManager(str(raw), str(processed))
    assert dm.blackout_root == blackout
    n = 121
    ts = 1600000000.0 + np.arange(n) / 10.0
    source = pd.DataFrame(
        {
            "timestamp": ts,
            "accel_x": np.ones(n),
            "gyro_x": np.zeros(n),
            "latitude_deg": np.linspace(52.4, 52.5, n),
            "longitude_deg": np.linspace(-1.9, -1.8, n),
            "speed_kmh": np.full(n, 30.0),
            "trip_id": "vw_test",
        }
    )
    cfg = EvaluationConfig.from_dict(
        {
            "blackout": {
                "min_trip_duration_s": 1.0,
                "min_pre_blackout_s": 1.0,
                "min_post_blackout_s": 1.0,
            }
        }
    )
    scen = build_scenarios(["vw_test"], [5.0], seed=1)[0]
    ds = create_blackout_dataset(source, scen, cfg)
    real = ds.frame.copy()
    real["reference_latitude_deg"] = np.linspace(52.4, 52.5, n)
    real["reference_speed_kmh"] = np.full(n, 31.0)
    path = _write_scenario(blackout, "5s", ds.scenario.scenario_id, real)
    return dm, blackout, ds.scenario.scenario_id, path


def test_list_and_load_blackout_scenario(populated):
    dm, blackout, sid, path = populated
    assert sid in dm.list_blackout_scenarios()
    loaded = dm.load_blackout_scenario(sid)
    assert len(loaded) == 121
    assert "gnss_available" in loaded.columns


def test_runtime_frame_strips_reference(populated):
    dm, _, sid, _ = populated
    loaded = dm.load_blackout_scenario(sid)
    runtime = dm.runtime_frame(loaded)
    assert not any(c.startswith("reference_") for c in runtime.columns)
    assert "accel_x" in runtime.columns


def test_reference_frame_isolates_offline_data(populated):
    dm, _, sid, _ = populated
    loaded = dm.load_blackout_scenario(sid)
    ref = dm.reference_frame(loaded)
    expected = {"timestamp"} | {c for c in loaded.columns if c.startswith("reference_")}
    assert set(ref.columns) == expected
    assert "accel_x" not in ref.columns
    assert "gnss_available" not in ref.columns


def test_metadata_loading(populated):
    dm, _, sid, _ = populated
    meta = dm.blackout_scenario_metadata(sid)
    assert meta["scenario_id"] == sid
    assert meta["n_rows"] == 121


def test_unknown_scenario_raises(populated):
    dm, _, _, _ = populated
    with pytest.raises(FileNotFoundError):
        dm.load_blackout_scenario("nope__blk5s_00")