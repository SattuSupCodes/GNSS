"""Road-network loading (D-S8).

Loads road polylines from GeoJSON (LineString / MultiLineString) into the
local ENU frame used by the navigation backend, or directly from ENU
polylines, and builds a :class:`~src.navigation.map_matching.road_graph.RoadGraph`.
"""

from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

from src.navigation.core.math_utils import LocalENU
from src.navigation.map_matching.road_graph import RoadGraph

EARTH_RADIUS_M = 6_378_137.0


def polylines_from_geojson(
    geojson,
) -> List[List[Tuple[float, float]]]:
    """Extract ``[(lon, lat), ...]`` polylines from a GeoJSON object.

    Accepts a parsed ``FeatureCollection``, ``Feature`` or geometry dict.
    Coordinates may include altitude as a third component, which is ignored.
    """
    polylines: List[List[Tuple[float, float]]] = []

    geometries = []

    if isinstance(geojson, dict):
        gtype = geojson.get("type")
        if gtype == "FeatureCollection":
            for feature in geojson.get("features", []):
                geom = feature.get("geometry")
                if geom is not None:
                    geometries.append(geom)
        elif gtype == "Feature":
            geom = geojson.get("geometry")
            if geom is not None:
                geometries.append(geom)
        elif gtype is not None:
            geometries.append(geojson)
    elif isinstance(geojson, list):
        geometries = geojson

    for geometry in geometries:
        gtype = geometry.get("type")
        coordinates = geometry.get("coordinates", [])
        if gtype == "LineString":
            polylines.append(_to_polyline(coordinates))
        elif gtype == "MultiLineString":
            for line in coordinates:
                polylines.append(_to_polyline(line))
        elif gtype == "GeometryCollection":
            for sub in geometry.get("geometries", []):
                sub_polylines = polylines_from_geojson(sub)
                polylines.extend(sub_polylines)

    return [p for p in polylines if len(p) >= 2]


def _to_polyline(coordinates) -> List[Tuple[float, float]]:
    polyline = []
    for point in coordinates:
        if len(point) < 2:
            continue
        polyline.append((float(point[0]), float(point[1])))
    return polyline


def polylines_to_enu(
    polylines_lonlat: Sequence[Sequence[Tuple[float, float]]],
    origin_latitude: float,
    origin_longitude: float,
) -> List[List[Tuple[float, float]]]:
    """Convert WGS84 polylines to local ENU metres around an origin."""
    origin = LocalENU(origin_latitude, origin_longitude)
    enu_polylines = []
    for polyline in polylines_lonlat:
        enu = []
        for (lon, lat) in polyline:
            east, north = origin.to_local(lat, lon)
            enu.append((east, north))
        enu_polylines.append(enu)
    return enu_polylines


def load_road_graph(
    source_path: Optional[str] = None,
    geojson: Optional[dict] = None,
    origin_latitude: Optional[float] = None,
    origin_longitude: Optional[float] = None,
    oneway: bool = False,
) -> RoadGraph:
    """Build a :class:`RoadGraph` from GeoJSON (file path or parsed dict).

    When no GeoJSON source is given an empty graph is returned.
    """
    if geojson is None:
        if source_path is None:
            return RoadGraph()
        with open(source_path, "r", encoding="utf-8") as fh:
            geojson = json.load(fh)

    polylines = polylines_from_geojson(geojson)

    if origin_latitude is not None and origin_longitude is not None:
        polylines = polylines_to_enu(
            polylines,
            origin_latitude,
            origin_longitude,
        )

    return RoadGraph.from_polylines(polylines, oneway=oneway)


def load_road_graph_from_polylines(
    polylines_enu: Sequence[Sequence[Tuple[float, float]]],
    oneway: bool = False,
) -> RoadGraph:
    """Build a :class:`RoadGraph` directly from ENU polylines."""
    return RoadGraph.from_polylines(polylines_enu, oneway=oneway)