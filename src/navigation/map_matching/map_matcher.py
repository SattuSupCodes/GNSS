from dataclasses import dataclass
from typing import Iterable, Optional
import math

@dataclass(frozen=True)
class RoadCandidate:
    road_id: str
    east_m: float
    north_m: float
    heading_rad: float
    distance_m: float

class MapMatcher:
    """Map-matching hook.

    Supply candidates from an OSM/road-graph adapter later. The navigation engine only
    depends on this small interface, so map data implementation stays outside the EKF.
    """
    def match(self, east_m: float, north_m: float, heading_rad: float,
              candidates: Iterable[RoadCandidate]) -> Optional[RoadCandidate]:
        candidates = list(candidates)
        if not candidates:
            return None
        def score(c):
            dh = abs((c.heading_rad - heading_rad + math.pi) % (2*math.pi) - math.pi)
            return c.distance_m + 5.0 * dh
        return min(candidates, key=score)
