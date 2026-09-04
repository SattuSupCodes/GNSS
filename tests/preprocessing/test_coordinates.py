"""Tests for WGS84 / ECEF / ENU coordinate transforms."""

from __future__ import annotations

import numpy as np
import pytest

from src.preprocessing.coordinate_transforms import (
    add_local_enu_columns,
    ecef_to_geodetic,
    enu_to_geodetic,
    geodetic_to_ecef,
    geodetic_to_enu,
    heading_from_enu,
)


def test_geodetic_ecef_roundtrip():
    lat, lon, alt = 52.5, -1.9, 90.0
    x, y, z = geodetic_to_ecef(lat, lon, alt)
    lat2, lon2, alt2 = ecef_to_geodetic(x, y, z)
    assert lat2 == pytest.approx(lat, abs=1e-9)
    assert lon2 == pytest.approx(lon, abs=1e-9)
    assert alt2 == pytest.approx(alt, abs=1e-6)


def test_enu_geodetic_roundtrip():
    ref = (52.5, -1.9, 90.0)
    east, north, up = 123.4, -56.7, 2.0
    lat, lon, alt = enu_to_geodetic(east, north, up, *ref)
    e2, n2, u2 = geodetic_to_enu(lat, lon, alt, *ref)
    assert e2 == pytest.approx(east, abs=1e-3)
    assert n2 == pytest.approx(north, abs=1e-3)
    assert u2 == pytest.approx(up, abs=1e-3)


def test_heading_from_enu_known_angles():
    # pure north -> 0, pure east -> 90
    assert heading_from_enu(np.array([0.0]), np.array([1.0]))[0] == pytest.approx(0.0)
    assert heading_from_enu(np.array([1.0]), np.array([0.0]))[0] == pytest.approx(90.0)
    assert heading_from_enu(np.array([0.0]), np.array([-1.0]))[0] == pytest.approx(180.0)


def test_add_local_enu_columns_canonical_trip(canonical_trip):
    df = canonical_trip.copy()
    out = add_local_enu_columns(df)
    assert {"pos_east_m", "pos_north_m", "pos_up_m"}.issubset(out.columns)
    # first fix sits at the origin
    first = out["latitude_deg"].first_valid_index()
    assert out.loc[first, "pos_east_m"] == pytest.approx(0.0, abs=1e-6)
    assert out.loc[first, "pos_north_m"] == pytest.approx(0.0, abs=1e-6)


def test_ecef_scalar_and_array_same_result():
    lat, lon, alt = 0.0, 0.0, 0.0
    x1, y1, z1 = geodetic_to_ecef(lat, lon, alt)
    x2, y2, z2 = geodetic_to_ecef([lat], [lon], [alt])
    assert x2[0] == pytest.approx(x1)
    assert y2[0] == pytest.approx(y1)
    assert z2[0] == pytest.approx(z1)