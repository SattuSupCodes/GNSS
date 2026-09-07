"""Map-matching facade (D-S8).

The navigation engine depends only on this small interface:

    MapMatcher.match(...)            nearest plausible road for one pose
    MapMatcher.match_sequence(...)   HMM Viterbi decode over a pose trace

Road-network data lives behind :class:`~src.navigation.map_matching.road_graph.RoadGraph`
and is fed either as explicit candidates (``Iterable[RoadCandidate]``) or
generated from the graph automatically when the matcher owns one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from src.navigation.map_matching.candidate_generation import generate_candidates
from src.navigation.map_matching.hmm_matcher import HMMMatcher, HMMPose, MapMatchResult
from src.navigation.map_matching.road_candidate import RoadCandidate
from src.navigation.map_matching.road_graph import RoadGraph


class MapMatcher:
    """Graph-aware nearest-road / HMM map matcher facade."""

    def __init__(
        self,
        graph: RoadGraph | None = None,
        candidate_radius_m: float = 50.0,
        max_candidates: int = 5,
        heading_weight: float = 5.0,
        sigma_distance_m: float = 5.0,
        sigma_heading_rad: float = 0.35,
        transition_gamma: float = 0.02,
        distance_tolerance_m: float = 5.0,
    ):
        self.graph = graph
        self.candidate_radius_m = float(candidate_radius_m)
        self.max_candidates = int(max_candidates)
        self.heading_weight = float(heading_weight)
        self.sigma_distance_m = float(sigma_distance_m)
        self.sigma_heading_rad = float(sigma_heading_rad)
        self.transition_gamma = float(transition_gamma)
        self.distance_tolerance_m = float(distance_tolerance_m)

    # ------------------------------------------------------------------ #
    # Single-pose matching
    # ------------------------------------------------------------------ #

    def match(
        self,
        east_m: float,
        north_m: float,
        heading_rad: float,
        candidates: Optional[Iterable[RoadCandidate]] = None,
    ) -> Optional[RoadCandidate]:
        """Nearest plausible road candidate.

        ``candidates`` may be omitted when the matcher owns a road graph; in
        that case they are generated on the fly within ``candidate_radius_m``.
        """
        if candidates is None:
            if self.graph is None:
                return None
            candidates = generate_candidates(
                self.graph,
                east_m,
                north_m,
                radius_m=self.candidate_radius_m,
                max_candidates=self.max_candidates,
            )

        candidates = list(candidates)
        if not candidates:
            return None

        def score(c: RoadCandidate) -> float:
            dh = abs(
                (c.heading_rad - heading_rad + math.pi) % (2.0 * math.pi) - math.pi
            )
            return c.distance_m + self.heading_weight * dh

        return min(candidates, key=score)

    # ------------------------------------------------------------------ #
    # Sequence matching (HMM)
    # ------------------------------------------------------------------ #

    def match_sequence(
        self,
        poses: Sequence[HMMPose],
    ) -> Optional[MapMatchResult]:
        """HMM Viterbi decode over a sequence of poses (needs a graph)."""
        if self.graph is None:
            return None
        hmm = HMMMatcher(
            self.graph,
            sigma_distance_m=self.sigma_distance_m,
            sigma_heading_rad=self.sigma_heading_rad,
            candidate_radius_m=self.candidate_radius_m,
            max_candidates=self.max_candidates,
            transition_gamma=self.transition_gamma,
            distance_tolerance_m=self.distance_tolerance_m,
        )
        return hmm.match_sequence(poses)