"""Road candidate generation (D-S8).

Given an estimated position and heading, generate nearby ``RoadCandidate``
objects: the closest point on every road edge within a search radius, the
edge's compass heading, and the perpendicular distance.
"""

from __future__ import annotations

import math
from typing import List, Optional

from src.navigation.map_matching.road_candidate import RoadCandidate
from src.navigation.map_matching.road_graph import RoadGraph


def _project_point_on_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> tuple[float, float, float, float]:
    """Project ``P`` onto segment ``AB``.

    Returns ``(t, closest_east, closest_north, distance)`` where ``t`` is
    the clamped along-segment parameter in ``[0, 1]``.
    """
    abx = bx - ax
    aby = by - ay
    denom = abx * abx + aby * aby
    if denom < 1e-12:
        return 0.0, ax, ay, math.hypot(px - ax, py - ay)

    t = ((px - ax) * abx + (py - ay) * aby) / denom
    t = min(max(t, 0.0), 1.0)
    cx = ax + t * abx
    cy = ay + t * aby
    dist = math.hypot(px - cx, py - cy)
    return t, cx, cy, dist


def generate_candidates(
    graph: RoadGraph,
    east_m: float,
    north_m: float,
    radius_m: float = 50.0,
    max_candidates: int = 5,
    heading_rad: Optional[float] = None,
) -> List[RoadCandidate]:
    """Candidates = nearest points on road edges within ``radius_m``."""
    candidates: List[RoadCandidate] = []

    for edge_id, edge in graph.edges.items():
        a = graph.node(edge.node_a)
        b = graph.node(edge.node_b)

        _t, cx, cy, dist = _project_point_on_segment(
            east_m, north_m, a.east_m, a.north_m, b.east_m, b.north_m
        )
        if dist > radius_m:
            continue

        candidates.append(
            RoadCandidate(
                road_id=edge_id,
                east_m=cx,
                north_m=cy,
                heading_rad=edge.heading_rad,
                distance_m=dist,
            )
        )

    candidates.sort(key=lambda c: c.distance_m)
    return candidates[:max_candidates]