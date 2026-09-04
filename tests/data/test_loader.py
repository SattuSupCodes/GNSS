"""Tests for the IO-VNBD loader using tiny synthetic CSV fixtures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.data_schema import (
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    MS_SINCE_START,
    SOURCE_FILE,
    SYNC_STATUS,
    TRIP_ID,
    TS_SEC,
    SyncStatus,
)
from src.data.io_vnbd_loader import (
    IOVNBDDataset,
    DatasetNotFoundError,
    UnresolvedLFSFileError,
    detect_sync_status,
    load_vehicle_csv,
    load_smartphone_csv,
)


def _write_smartphone_csv(path: Path, body: bytes) -> Path:
    path.write_bytes(body)
    return path


def _minimal_smartphone_csv() -> bytes:
    # Realistic header variants: UTF-8 byte pairs for degree/mu inside cp1252,
    # gyro Yaw/Pitch/Roll, "N / M" satellites string, leading-space headers.
    return (
        b"GPS LATITUDE (degrees), GPS LONGITUDE (degrees), GPS SPEED (Kmh), "
        b"GPS SATELLITES IN RANGE, TIME SINCE START (ms), "
        b"DATE (YYYY-MO-DD HH-MI-SS_SSS), ACCELEROMETER X (m/s\xb2), "
        b"ACCELEROMETER Y (m/s\xb2), ACCELEROMETER Z (m/s\xb2), "
        b"GYROSCOPE Yaw (rad/s), GYROSCOPE Pitch (rad/s), GYROSCOPE Roll (rad/s), "
        b"MAGNETIC FIELD X (\xce\xbcT), MAGNETIC FIELD Y (\xce\xbcT), "
        b"MAGNETIC FIELD Z (\xce\xbcT), ORIENTATION (Yaw) (\xc2\xb0), "
        b"ORIENTATION (Pitch) (\xc2\xb0), ORIENTATION (Roll ) (\xc2\xb0)\n"
        b"52.50, -1.90, 41.0, 25 / 25, 100, 2020-01-08 17:42:16:100, "
        b"0.60, -0.40, 9.80, 0.15, 0.10, -0.05, 10.0, 12.0, 14.0, "
        b"327.0, -12.0, 3.0\n"
    )


def test_load_smartphone_csv_remaps_and_parses(tmp_path):
    sync_dir = tmp_path / "Synchronised V abd S datasets" / "Vw (Driver E)"
    sync_dir.mkdir(parents=True)
    p = _write_smartphone_csv(sync_dir / "S-Vw16b.csv", _minimal_smartphone_csv())
    df = load_smartphone_csv(p)
    assert len(df) == 1
    # canonical remapped columns
    assert df[TRIP_ID].iloc[0] == "vw16b"
    assert df[SYNC_STATUS].iloc[0] == SyncStatus.SYNCHRONISED.value
    # mojibake-repaired headers landed on canonical gyro/mag/orientation cols
    assert GYRO_X in df.columns and GYRO_Y in df.columns and GYRO_Z in df.columns
    assert df[GYRO_X].iloc[0] == pytest.approx(0.15)
    assert "mag_x" in df.columns and df["mag_x"].iloc[0] == pytest.approx(10.0)
    assert "orientation_azimuth_deg" in df.columns
    assert df["orientation_azimuth_deg"].iloc[0] == pytest.approx(327.0)
    # "25 / 25" parsed to numeric 25
    assert df["gps_satellites"].iloc[0] == pytest.approx(25.0)
    # timestamp: '2020-01-08 17:42:16.100' (naive, read as UTC in pandas ns)
    expected_ts = (
        pd.Timestamp("2020-01-08 17:42:16.100", tz="UTC")
        .tz_convert("UTC")
        .timestamp()
    )
    assert df[TS_SEC].iloc[0] == pytest.approx(expected_ts, abs=1e-6)
    assert df[MS_SINCE_START].iloc[0] == pytest.approx(100.0)


def test_load_smartphone_csv_missing_file(tmp_path):
    with pytest.raises(DatasetNotFoundError):
        load_smartphone_csv(tmp_path / "nope.csv")


def test_lfs_pointer_detected(tmp_path):
    p = tmp_path / "S-x.csv"
    p.write_bytes(b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\n")
    with pytest.raises(UnresolvedLFSFileError):
        load_smartphone_csv(p)


def test_sync_status_detection():
    assert (
        detect_sync_status(Path("/a/Synchronised V abd S datasets/S-V.csv"))
        == SyncStatus.SYNCHRONISED
    )
    assert (
        detect_sync_status(Path("/a/Unsynchronised V and S Dataset/S-V.csv"))
        == SyncStatus.UNSYNCHRONISED
    )


def test_discovery_and_trip_ids(tmp_path):
    sync = tmp_path / "Synchronised V abd S datasets" / "Vw (Driver E)"
    sync.mkdir(parents=True)
    _write_smartphone_csv(sync / "S-Vw16b.csv", _minimal_smartphone_csv())
    unsync = tmp_path / "Unsynchronised V and S Dataset" / "S-Dataset"
    unsync.mkdir(parents=True)
    _write_smartphone_csv(unsync / "S-Vw16b.csv", _minimal_smartphone_csv())

    ds = IOVNBDDataset(str(tmp_path))
    assert len(ds.list_smartphone_files()) == 2
    assert ds.smartphone_trip_ids() == ["vw16b"]
    sp = ds.smartphone_file_for_trip("vw16b", SyncStatus.SYNCHRONISED)
    assert sp is not None and "Synchronised" in str(sp)


def test_vehicle_csv_is_reference_tagged(tmp_path):
    v = tmp_path / "V-Vw16b.csv"
    v.write_text(
        "No of GPS Satellites Available, Time Since Start of Day (seconds), "
        "Heading (degrees)\n10, 64000.5, 327.0\n",
        encoding="cp1252",
    )
    df = load_vehicle_csv(v, trip_id="vw16b")
    assert df["is_reference"].iloc[0] == True  # noqa: E712
    assert df[TS_SEC].iloc[0] == pytest.approx(64000.5)
    assert df[TRIP_ID].iloc[0] == "vw16b"


def test_no_data_raises(tmp_path):
    ds = IOVNBDDataset(str(tmp_path))
    with pytest.raises(DatasetNotFoundError):
        ds.check_smartphone_data_available()