import pytest

from src.navigation.core.math_utils import LocalENU
from src.navigation.map_matching.map_loader import (
    load_road_graph,
    load_road_graph_from_polylines,
    polylines_from_geojson,
    polylines_to_enu,
)

LAT0, LON0 = 52.5, -1.9


def test_polylines_from_geojson_extracts_lines():
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[LON0, LAT0], [LON0 + 0.001, LAT0]],
                },
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "MultiLineString",
                    "coordinates": [
                        [[LON0, LAT0], [LON0, LAT0 + 0.001]],
                    ],
                },
            },
        ],
    }
    polylines = polylines_from_geojson(geojson)
    assert len(polylines) == 2
    assert all(len(p) >= 2 for p in polylines)


def test_polylines_from_geojson_skips_short_lines():
    geojson = {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [[0, 0]]},
    }
    assert polylines_from_geojson(geojson) == []


def test_enu_conversion_origin_is_zero():
    enu = polylines_to_enu([[[LON0, LAT0], [LON0 + 0.001, LAT0]]], LAT0, LON0)
    polyline = enu[0]
    east0, north0 = polyline[0]
    assert east0 == pytest.approx(0.0, abs=1e-6)
    assert north0 == pytest.approx(0.0, abs=1e-6)
    # 0.001 deg at lat 52.5 => ~68 m east.
    assert polyline[1][0] == pytest.approx(68.0, abs=5.0)


def test_load_road_graph_builds_nodes_and_edges():
    graph = load_road_graph_from_polylines(
        [[(0.0, 0.0), (100.0, 0.0)], [(0.0, 0.0), (0.0, 100.0)]]
    )
    # Each polyline independently creates nodes, so two polylines sharing a
    # coordinate still produce distinct node ids (n0, n1) and (n2, n3).
    assert graph.num_nodes == 4
    assert graph.num_edges >= 4


def test_load_road_graph_from_geojson_dict():
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[LON0, LAT0], [LON0 + 0.001, LAT0]],
                },
            },
        ],
    }
    graph = load_road_graph(geojson=geojson, origin_latitude=LAT0, origin_longitude=LON0)
    assert graph.num_nodes == 2
    assert graph.num_edges >= 2


def test_shortest_path_length():
    from src.navigation.map_matching.road_graph import RoadGraph

    graph = RoadGraph()
    graph.add_node("a", 0.0, 0.0)
    graph.add_node("b", 100.0, 0.0)
    graph.add_node("c", 100.0, 50.0)
    graph.add_edge("e1", "a", "b")
    graph.add_edge("e2", "b", "c")

    assert graph.shortest_path_length("a", "c") == pytest.approx(150.0)
    assert graph.shortest_path_length("c", "a") == pytest.approx(150.0)
    assert graph.shortest_path_length("a", "missing") is None


def test_local_enu_roundtrip():
    enu = LocalENU(LAT0, LON0)
    east, north = enu.to_xy(52.55, -1.8)
    lat, lon = enu.to_ll(east, north)
    assert lat == pytest.approx(52.55, abs=1e-6)
    assert lon == pytest.approx(-1.8, abs=1e-6)