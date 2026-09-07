"""Hidden-Markov-Model map matcher (D-S8).

The matcher resolves the pipeline

    Estimated Position -> Nearby Road Candidates -> Heading Compatibility ->
    Distance Compatibility -> Road Connectivity -> Most Likely Road ->

using a Viterbi decoding over time:

   * emission   : perpendicular distance + heading difference to each edge
   * transition : road-network connectivity between consecutive edges plus a
     penalty proportional to the mismatch between the observed movement and
     the geometric candidate distance (a vehicle cannot teleport/change
     direction across disconnected roads).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence

from src.navigation.core.math_utils import wrap_angle
from src.navigation.map_matching.candidate_generation import generate_candidates
from src.navigation.map_matching.road_candidate import RoadCandidate
from src.navigation.map_matching.road_graph import RoadGraph

NEG_INF = -1e12


@dataclass
class HMMPose:
    east_m: float
    north_m: float
    heading_rad: float = 0.0
    timestamp: float = 0.0
    uncertainty_m: float = 5.0


@dataclass
class MapMatchResult:
    timestamps: List[float]
    matched_poses: List[RoadCandidate]
    matched_road_ids: List[str]
    posterior: float


class HMMMatcher:
    def __init__(
        self,
        graph: RoadGraph,
        sigma_distance_m: float = 5.0,
        sigma_heading_rad: float = 0.35,
        candidate_radius_m: float = 50.0,
        max_candidates: int = 5,
        transition_gamma: float = 0.02,
        distance_tolerance_m: float = 5.0,
    ):
        self.graph = graph
        self.sigma_distance_m = float(sigma_distance_m)
        self.sigma_heading_rad = float(sigma_heading_rad)
        self.candidate_radius_m = float(candidate_radius_m)
        self.max_candidates = int(max_candidates)
        self.transition_gamma = float(transition_gamma)
        self.distance_tolerance_m = float(distance_tolerance_m)

    # ------------------------------------------------------------------ #
    # Emission
    # ------------------------------------------------------------------ #

    def _emission_log(self, pose: HMMPose, candidate: RoadCandidate) -> float:
        distance_term = -0.5 * (
            candidate.distance_m / max(self.sigma_distance_m, 1e-6)
        ) ** 2
        d_heading = abs(
            wrap_angle(candidate.heading_rad - pose.heading_rad)
        )
        heading_term = -0.5 * (
            d_heading / max(self.sigma_heading_rad, 1e-6)
        ) ** 2
        return distance_term + heading_term

    # ------------------------------------------------------------------ #
    # Transition
    # ------------------------------------------------------------------ #

    def _transition_log(
        self,
        prev_pose: HMMPose,
        prev_candidate: RoadCandidate,
        pose: HMMPose,
        candidate: RoadCandidate,
    ) -> float:
        observed = math.hypot(
            pose.east_m - prev_pose.east_m,
            pose.north_m - prev_pose.north_m,
        )
        candidates_dist = math.hypot(
            candidate.east_m - prev_candidate.east_m,
            candidate.north_m - prev_candidate.north_m,
        )

        # Road connectivity: the two edges must be reachable in the network.
        # Derive representative nodes from the edge records.
        a_node = prev_candidate.road_id
        b_node = candidate.road_id

        def _endpoint_node(edge_id: str, side: str) -> str:
            edge = self.graph.edge(edge_id)
            return edge.node_a if side == "a" else edge.node_b

        route = self.graph.shortest_path_length(
            _endpoint_node(a_node, "a"),
            _endpoint_node(b_node, "b"),
        )
        if route is None:
            return NEG_INF

        mismatch = abs(candidates_dist - observed)
        mismatch = max(mismatch - self.distance_tolerance_m, 0.0)
        return -self.transition_gamma * mismatch

    # ------------------------------------------------------------------ #
    # Viterbi
    # ------------------------------------------------------------------ #

    def match_sequence(
        self,
        poses: Sequence[HMMPose],
    ) -> Optional[MapMatchResult]:
        if not poses or self.graph is None:
            return None

        all_candidates: List[List[RoadCandidate]] = []
        for pose in poses:
            candidates = generate_candidates(
                self.graph,
                pose.east_m,
                pose.north_m,
                radius_m=self.candidate_radius_m,
                max_candidates=self.max_candidates,
                heading_rad=pose.heading_rad,
            )
            all_candidates.append(candidates)

        # Drop empty samples (no road within radius).
        for i, candidates in enumerate(all_candidates):
            if not candidates:
                return None

        n_steps = len(poses)
        n_cands = [len(c) for c in all_candidates]

        delta = [[NEG_INF] * n for n in n_cands]
        psi = [[0] * n for n in n_cands]

        for j, candidate in enumerate(all_candidates[0]):
            delta[0][j] = self._emission_log(poses[0], candidate)

        for t in range(1, n_steps):
            prev_pose = poses[t - 1]
            pose = poses[t]
            for j, candidate in enumerate(all_candidates[t]):
                best_score = NEG_INF
                best_prev = 0
                for i, prev_candidate in enumerate(all_candidates[t - 1]):
                    score = (
                        delta[t - 1][i]
                        + self._emission_log(pose, candidate)
                        + self._transition_log(
                            prev_pose, prev_candidate, pose, candidate
                        )
                    )
                    if score > best_score:
                        best_score = score
                        best_prev = i
                delta[t][j] = best_score
                psi[t][j] = best_prev

        # Backtrack.
        best_index = max(range(n_cands[-1]), key=lambda j: delta[-1][j])
        posterior = delta[-1][best_index]

        path = [best_index]
        for t in range(n_steps - 1, 0, -1):
            best_index = psi[t][best_index]
            path.append(best_index)
        path.reverse()

        timestamps: List[float] = []
        matched_poses: List[RoadCandidate] = []
        matched_roads: List[str] = []
        for t, index in enumerate(path):
            timestamps.append(float(poses[t].timestamp))
            matched_poses.append(all_candidates[t][index])
            matched_roads.append(all_candidates[t][index].road_id)

        return MapMatchResult(
            timestamps=timestamps,
            matched_poses=matched_poses,
            matched_road_ids=matched_roads,
            posterior=float(posterior),
        )

    @staticmethod
    def pose_from_state(state) -> HMMPose:
        return HMMPose(
            east_m=float(state.east_m),
            north_m=float(state.north_m),
            heading_rad=float(state.heading_rad),
            timestamp=float(getattr(state, "timestamp", 0.0)),
        )