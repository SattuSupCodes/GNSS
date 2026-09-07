"""Road candidate value type (D-S8)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoadCandidate:
    road_id: str
    east_m: float
    north_m: float
    heading_rad: float
    distance_m: float