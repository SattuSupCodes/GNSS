import math

import pytest

from src.navigation.map_matching.candidate_generation import generate_candidates
from src.navigation.map_matching.hmm_matcher import HMMMatcher, HMMPose
from src.navigation.map_matching.map_matcher import MapMatcher, RoadCandidate
from src.navigation.map_matching.road_graph import RoadGraph


def _l_graph() -> RoadGraph:
    """Horizontal road east (heading 90 deg), vertical road north from the
    corner at (100, 0)."""
    graph = RoadGraph()
    graph.add_node("n0", 0.0, 0.0)
    graph.add_node("n1", 100.0, 0.0)
    graph.add_node("n2", 100.0, 100.0)
    graph.add_edge("e_h", "n0", "n1")
    graph.add_edge("e_v", "n1", "n2")
    return graph


def test_candidate_generation_projects_to_segment():
    graph = _l_graph()
    candidates = generate_candidates(graph, 50.0, 4.0, radius_m=20.0)
    assert candidates
    best = candidates[0]
    assert best.east_m == pytest.approx(50.0, abs=1e-6)
    assert best.north_m == pytest.approx(0.0, abs=1e-6)
    assert best.distance_m == pytest.approx(4.0, abs=1e-6)
    assert best.heading_rad == pytest.approx(math.pi / 2, abs=1e-6)


def test_generate_candidates_limits_and_radius():
    graph = _l_graph()
    assert generate_candidates(graph, 50.0, 0.0, radius_m=5.0, max_candidates=2)
    assert generate_candidates(graph, 500.0, 500.0, radius_m=5.0) == []


def test_single_match_returns_nearest_road():
    graph = _l_graph()
    matcher = MapMatcher(graph)
    candidate = matcher.match(10.0, 2.0, math.pi / 2)
    assert candidate is not None
    assert candidate.road_id == "e_h"


def test_matching_without_graph_returns_none():
    matcher = MapMatcher()
    assert matcher.match(10.0, 10.0, 0.0) is None


def test_hmm_follows_straight_road():
    graph = _l_graph()
    matcher = HMMMatcher(graph)
    poses = [
        HMMPose(east_m=10.0, north_m=2.0, heading_rad=math.pi / 2, timestamp=0.0),
        HMMPose(east_m=30.0, north_m=2.0, heading_rad=math.pi / 2, timestamp=1.0),
        HMMPose(east_m=70.0, north_m=2.0, heading_rad=math.pi / 2, timestamp=2.0),
    ]
    result = matcher.match_sequence(poses)
    assert result is not None
    assert set(result.matched_road_ids) == {"e_h"}
    assert result.posterior < 0.0


def test_hmm_handles_turn_at_corner():
    graph = _l_graph()
    matcher = HMMMatcher(graph, candidate_radius_m=8.0)
    poses = [
        HMMPose(east_m=80.0, north_m=0.5, heading_rad=math.pi / 2, timestamp=0.0),
        HMMPose(east_m=99.0, north_m=0.5, heading_rad=math.pi / 2, timestamp=1.0),
        HMMPose(east_m=101.0, north_m=20.0, heading_rad=0.0, timestamp=2.0),
        HMMPose(east_m=101.0, north_m=60.0, heading_rad=0.0, timestamp=3.0),
    ]
    result = matcher.match_sequence(poses)
    assert result is not None
    assert result.matched_road_ids[0] == "e_h"
    assert result.matched_road_ids[-1] == "e_v"
    assert len(result.matched_poses) == 4


def test_hmm_returns_none_on_empty():
    graph = _l_graph()
    assert HMMMatcher(graph).match_sequence([]) is None


def test_map_matcher_match_sequence_requires_graph():
    matcher = MapMatcher()
    assert matcher.match_sequence([]) is None


def test_map_matcher_sequence_with_graph():
    graph = _l_graph()
    matcher = MapMatcher(graph)
    poses = [
        HMMPose(east_m=5.0, north_m=1.0, heading_rad=math.pi / 2, timestamp=0.0),
        HMMPose(east_m=15.0, north_m=1.0, heading_rad=math.pi / 2, timestamp=1.0),
    ]
    result = matcher.match_sequence(poses)
    assert result is not None
    assert result.matched_road_ids == ["e_h", "e_h"]


def test_explicit_candidates_override_graph():
    graph = _l_graph()
    matcher = MapMatcher(graph)
    far = RoadCandidate("e_v", 100.0, 50.0, 0.0, 100.0)
    result = matcher.match(0.0, 0.0, 0.0, candidates=[far])
    assert result == far