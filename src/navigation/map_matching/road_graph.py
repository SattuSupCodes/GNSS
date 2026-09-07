"""Lightweight road network graph (D-S8).

A ``RoadGraph`` is built from road polylines. Each polyline becomes a chain
of directed ``RoadEdge`` records between ``RoadNode`` vertices. The graph is
kept intentionally small and dependency-free (numpy-only); it is not a
replacement for a full GIS stack, but it is enough for HMM candidate
generation and shortest-path connectivity checks.

Coordinates are in the local ENU frame (metres) used by the navigation
backend; see ``map_loader.py`` for the conversion from GeoJSON.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class RoadNode:
    node_id: str
    east_m: float
    north_m: float


@dataclass
class RoadEdge:
    edge_id: str
    node_a: str
    node_b: str
    length_m: float = 0.0
    heading_rad: float = 0.0  # compass bearing from A -> B


class RoadGraph:
    def __init__(self):
        self.nodes: Dict[str, RoadNode] = {}
        self.edges: Dict[str, RoadEdge] = {}
        self._adj: Dict[str, List[str]] = {}
        self._out: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def add_node(self, node_id: str, east_m: float, north_m: float) -> None:
        self.nodes[node_id] = RoadNode(node_id, float(east_m), float(north_m))

    def add_edge(
        self,
        edge_id: str,
        node_a: str,
        node_b: str,
        oneway: bool = False,
    ) -> None:
        if node_a not in self.nodes or node_b not in self.nodes:
            raise KeyError("both endpoints must be added as nodes first")

        a, b = self.nodes[node_a], self.nodes[node_b]
        de, dn = b.east_m - a.east_m, b.north_m - a.north_m
        length = float(math.hypot(de, dn))
        heading = math.atan2(de, dn)  # compass from A -> B

        edge = RoadEdge(
            edge_id=edge_id,
            node_a=node_a,
            node_b=node_b,
            length_m=max(length, 1e-9),
            heading_rad=heading,
        )
        self.edges[edge_id] = edge

        if edge_id not in self._out:
            self._out[node_a] = self._out.get(node_a, []) + [edge_id]

        # Connectivity: append undirected so shortest paths work for
        # double-heavy roads as well.
        self._adj[node_a] = self._adj.get(node_a, []) + [node_b]
        if not oneway:
            self._adj[node_b] = self._adj.get(node_b, []) + [node_a]
            rev = RoadEdge(
                edge_id=f"{edge_id}_rev",
                node_a=node_b,
                node_b=node_a,
                length_m=edge.length_m,
                heading_rad=(heading + math.pi) % (2.0 * math.pi) - math.pi,
            )
            self.edges[rev.edge_id] = rev

    @classmethod
    def from_polylines(
        cls,
        polylines,
        node_id_prefix: str = "n",
        edge_id_prefix: str = "e",
        oneway: bool = False,
    ) -> "RoadGraph":
        """Build a graph from a list of ``[(east, north), ...]`` polylines."""
        graph = cls()
        node_counter = 0

        for polyline in polylines:
            if len(polyline) < 2:
                continue
            chain = []
            for (east, north) in polyline:
                node_id = f"{node_id_prefix}{node_counter}"
                node_counter += 1
                graph.add_node(node_id, east, north)
                chain.append(node_id)

            edge_id = None
            for i in range(len(chain) - 1):
                edge_id = f"{edge_id_prefix}{len(graph.edges)}"
                graph.add_edge(edge_id, chain[i], chain[i + 1], oneway=oneway)

        return graph

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    def neighbors(self, node_id: str) -> List[str]:
        return list(self._adj.get(node_id, []))

    def node(self, node_id: str) -> RoadNode:
        return self.nodes[node_id]

    def edge(self, edge_id: str) -> RoadEdge:
        return self.edges[edge_id]

    # ------------------------------------------------------------------ #
    # Routing (for HMM transitions / connectivity)
    # ------------------------------------------------------------------ #

    def shortest_path_length(
        self,
        start_node: str,
        goal_node: str,
    ) -> Optional[float]:
        """Shortest path length in metres between two graph nodes (Dijkstra)."""
        if start_node not in self.nodes or goal_node not in self.nodes:
            return None
        if start_node == goal_node:
            return 0.0

        import heapq

        dist = {start_node: 0.0}
        heap = [(0.0, start_node)]

        while heap:
            d, node = heapq.heappop(heap)
            if d > dist.get(node, float("inf")):
                continue
            if node == goal_node:
                return d
            for neighbor in self.neighbors(node):
                edge_id = self._find_edge(node, neighbor)
                if edge_id is None:
                    continue
                nd = d + self.edges[edge_id].length_m
                if nd < dist.get(neighbor, float("inf")):
                    dist[neighbor] = nd
                    heapq.heappush(heap, (nd, neighbor))

        return None

    def _find_edge(self, node_a: str, node_b: str) -> Optional[str]:
        """Return the edge_id connecting ``node_a`` -> ``node_b`` (either dir)."""
        for edge_id in self._out.get(node_a, []):
            edge = self.edges[edge_id]
            if edge.node_b == node_b:
                return edge_id
        for edge_id in self._out.get(node_b, []):
            edge = self.edges[edge_id]
            if edge.node_b == node_a:
                return edge_id
        return None