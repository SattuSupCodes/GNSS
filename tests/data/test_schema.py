"""Tests for the canonical data schema and column mapping."""

from __future__ import annotations

from src.data.data_schema import (
    IOVNBD_SMARTPHONE_COLUMN_MAP,
    ACCEL_X,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    MAG_X,
    METADATA_COLUMNS,
    SENSOR_COLUMNS,
    SYNC_STATUS,
    TRIP_ID,
    TS_SEC,
    TripMetadata,
    SyncStatus,
    normalize_source_column,
)


def test_timestamp_is_first_sensor_column():
    assert SENSOR_COLUMNS[0] == TS_SEC


def test_metadata_is_disjoint_from_sensors():
    assert not set(METADATA_COLUMNS) & set(SENSOR_COLUMNS)


def test_smartphone_map_keys_all_normalize_to_self():
    """Every map key must round-trip through normalize_source_column."""
    for key in IOVNBD_SMARTPHONE_COLUMN_MAP:
        assert normalize_source_column(key) == key, key


def test_normalize_repairs_utf8_mojibake_degree():
    # 0xC2 0xB0 is UTF-8 for the degree sign read back as cp1252 ("Â°").
    assert normalize_source_column(" GPS ORIENTATION (\u00c2\u00b0)") == (
        "GPS ORIENTATION (\u00b0)"
    )


def test_normalize_repairs_utf8_mojibake_mu():
    # 0xCE 0xBC is UTF-8 for Greek small mu read back as cp1252 ("Î¼").
    out = normalize_source_column(" MAGNETIC FIELD X (\u00ce\u00bcT)")
    assert out in IOVNBD_SMARTPHONE_COLUMN_MAP
    assert IOVNBD_SMARTPHONE_COLUMN_MAP[out] == MAG_X


def test_both_gyro_naming_schemes_mapped():
    assert normalize_source_column(" GYROSCOPE YAW (rad/s)") in (
        IOVNBD_SMARTPHONE_COLUMN_MAP
    )
    assert normalize_source_column(" GYROSCOPE X (rad/s)") in (
        IOVNBD_SMARTPHONE_COLUMN_MAP
    )
    assert normalize_source_column(" GYROSCOPE Z (rad/s)") in (
        IOVNBD_SMARTPHONE_COLUMN_MAP
    )


def test_yaw_pitch_roll_map_to_canonical_xyz():
    for src, dst in (
        ("GYROSCOPE YAW (RAD/S)", GYRO_X),
        ("GYROSCOPE PITCH (RAD/S)", GYRO_Y),
        ("GYROSCOPE ROLL (RAD/S)", GYRO_Z),
    ):
        assert IOVNBD_SMARTPHONE_COLUMN_MAP[src] == dst


def test_accel_unit_superscript_two():
    out = normalize_source_column(" ACCELEROMETER X (m/s\u00b2)")
    assert IOVNBD_SMARTPHONE_COLUMN_MAP[out] == ACCEL_X


def test_trip_metadata_to_dict_roundtrip():
    meta = TripMetadata(
        trip_id="vw16b",
        sync_status=SyncStatus.SYNCHRONISED,
        driver="E",
        category="VW",
        source_files=["S-Vw16b.csv"],
        n_samples=10,
    )
    d = meta.to_dict()
    assert d["trip_id"] == "vw16b"
    assert d["sync_status"] == "synchronised"
    assert d["driver"] == "E"
    assert d["n_samples"] == 10


def test_sync_status_values():
    assert SyncStatus.SYNCHRONISED.value == "synchronised"
    assert SyncStatus.UNSYNCHRONISED.value == "unsynchronised"


def test_column_name_constants():
    assert TRIP_ID == "trip_id"
    assert SYNC_STATUS == "sync_status"