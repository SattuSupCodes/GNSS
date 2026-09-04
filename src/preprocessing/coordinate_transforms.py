"""Coordinate transforms for GNSS positions and headings.

Provides WGS84 geodetic <-> ECEF <-> local ENU (north/east/up) conversions and
heading conventions used by the navigation module. Outputs coordinates in
meters relative to a trip-local origin so downstream dead-reckoning math lives
in a flat local frame.

All functions accept scalars or arrays.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from ..data.data_schema import GNSS_LAT, GNSS_LON, GNSS_HEADING

A_WGS84 = 6378137.0
F_WGS84 = 1.0 / 298.257223563
E2_WGS84 = F_WGS84 * (2.0 - F_WGS84)


def geodetic_to_ecef(lat_deg, lon_deg, alt_m) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert WGS84 geodetic to ECEF XYZ (meters). Returns (x, y, z)."""
    lat, lon, alt = np.deg2rad(lat_deg), np.deg2rad(lon_deg), alt_m
    n = A_WGS84 / np.sqrt(1.0 - E2_WGS84 * np.sin(lat) ** 2)
    x = (n + alt) * np.cos(lat) * np.cos(lon)
    y = (n + alt) * np.cos(lat) * np.sin(lon)
    z = (n * (1.0 - E2_WGS84) + alt) * np.sin(lat)
    return x, y, z


def ecef_to_geodetic(x, y, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ECEF XYZ (meters) -> (lat_deg, lon_deg, alt_m)."""

    def _iterative(xx, yy, zz):
        lon = np.arctan2(yy, xx)
        lat = np.arctan2(zz, np.hypot(xx, yy))
        alt = np.zeros_like(lat)
        for _ in range(8):
            n = A_WGS84 / np.sqrt(1.0 - E2_WGS84 * np.sin(lat) ** 2)
            alt = (np.hypot(xx, yy) / np.cos(lat)) - n
            lat = np.arctan2(
                zz, np.hypot(xx, yy) * (1.0 - E2_WGS84 * n / (n + alt))
            )
        return lat, lon, alt

    x, y, z = np.asarray(x, dtype=float), np.asarray(y, dtype=float), np.asarray(z, dtype=float)
    lat, lon, alt = _iterative(x, y, z)
    return np.rad2deg(lat), np.rad2deg(lon), alt


def geodetic_to_enu(
    lat_deg, lon_deg, alt_m,
    ref_lat_deg, ref_lon_deg, ref_alt_m=0.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """WGS84 -> local ENU in meters relative to a reference point."""
    x, y, z = geodetic_to_ecef(lat_deg, lon_deg, alt_m)
    xr, yr, zr = geodetic_to_ecef(ref_lat_deg, ref_lon_deg, ref_alt_m)
    lat0, lon0 = np.deg2rad(ref_lat_deg), np.deg2rad(ref_lon_deg)
    dx, dy, dz = x - xr, y - yr, z - zr
    east = -np.sin(lon0) * dx + np.cos(lon0) * dy
    north = (
        -np.sin(lat0) * np.cos(lon0) * dx
        - np.sin(lat0) * np.sin(lon0) * dy
        + np.cos(lat0) * dz
    )
    up = (
        np.cos(lat0) * np.cos(lon0) * dx
        + np.cos(lat0) * np.sin(lon0) * dy
        + np.sin(lat0) * dz
    )
    return east, north, up


def enu_to_geodetic(
    east, north, up,
    ref_lat_deg, ref_lon_deg, ref_alt_m=0.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Local ENU (meters) -> WGS84 geodetic."""
    lat0, lon0 = np.deg2rad(ref_lat_deg), np.deg2rad(ref_lon_deg)
    xr, yr, zr = geodetic_to_ecef(ref_lat_deg, ref_lon_deg, ref_alt_m)
    dx = (
        -np.sin(lon0) * east - np.sin(lat0) * np.cos(lon0) * north
        + np.cos(lat0) * np.cos(lon0) * up
    )
    dy = (
        np.cos(lon0) * east - np.sin(lat0) * np.sin(lon0) * north
        + np.cos(lat0) * np.sin(lon0) * up
    )
    dz = np.cos(lat0) * north + np.sin(lat0) * up
    return ecef_to_geodetic(xr + dx, yr + dy, zr + dz)


def heading_from_enu(east, north) -> np.ndarray:
    """Local ENU (east, north meters) -> bearing in degrees clockwise from
    north (0..360), matching the GPS course convention."""
    h = np.rad2deg(np.arctan2(east, north)) % 360.0
    return h


def add_local_enu_columns(
    df: pd.DataFrame, ref_lat_deg: Optional[float] = None, ref_lon_deg: Optional[float] = None
) -> pd.DataFrame:
    """Append ``pos_east_m`` / ``pos_north_m`` / ``pos_up_m`` columns.

    Origin defaults to the first valid GNSS fix in the frame.
    """
    if GNSS_LAT not in df.columns or GNSS_LON not in df.columns:
        return df
    lat = pd.to_numeric(df[GNSS_LAT], errors="coerce")
    lon = pd.to_numeric(df[GNSS_LON], errors="coerce")
    alt = (
        pd.to_numeric(df.get("altitude_m"), errors="coerce")
        if "altitude_m" in df.columns
        else pd.Series(0.0, index=df.index)
    )
    first = None
    if ref_lat_deg is None or ref_lon_deg is None:
        m = lat.notna() & lon.notna()
        if m.any():
            first = (float(lat[m].iloc[0]), float(lon[m].iloc[0]))
    rlat = ref_lat_deg if ref_lat_deg is not None else (first[0] if first else 0.0)
    rlon = ref_lon_deg if ref_lon_deg is not None else (first[1] if first else 0.0)

    e, n, u = geodetic_to_enu(
        lat.fillna(rlat), lon.fillna(rlon), alt.fillna(0.0), rlat, rlon, 0.0
    )
    out = df.copy()
    out["pos_east_m"] = e
    out["pos_north_m"] = n
    out["pos_up_m"] = u
    out["pos_east_m"] = out["pos_east_m"].where(lat.notna() & lon.notna())
    out["pos_north_m"] = out["pos_north_m"].where(lat.notna() & lon.notna())
    out["pos_up_m"] = out["pos_up_m"].where(lat.notna() & lon.notna())
    return out