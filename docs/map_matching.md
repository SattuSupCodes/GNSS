# Map Matching (D-S8)

The map-matching subsystem constrains the fused GNSS+INS solution to a road
network. It lives under `src/navigation/map_matching/` and is integrated
through `MapMatcher`, which the `IDREngine` calls on its `update_map_match`.

```
Estimated Position (EKF/UKF)
   -> Candidate Generation (project to nearby road segments)
   -> Heading / Distance compatibility
   -> Road-network connectivity (Dijkstra shortest path)
   -> Viterbi decode over time (HMM)
   -> Corrected pose fed back via re-localization
```

## Components

### `road_graph.py`
A lightweight, dependency-free `RoadGraph`:
* `RoadNode` (id, east, north) and directed `RoadEdge` (id, A, B, length,
  compass heading).
* `from_polylines` builds a graph from `[(east, north), ...]` polylines,
  adding forward + reverse edges unless `oneway=True`.
* `shortest_path_length(a, b)` uses Dijkstra (heapq) for connectivity checks
  used by the HMM transition model.
* Nodes are per-polyline (two polylines sharing a coordinate do not merge).

### `candidate_generation.py`
`generate_candidates(graph, east, north, radius_m, max_candidates, heading)`
projects the estimated position onto every road edge within `radius_m`
and returns the closest `RoadCandidate` objects, each with the road id, the
projected point, the segment's compass heading and the perpendicular distance.

### `hmm_matcher.py`
`HMMMatcher` performs Viterbi decoding over a pose sequence:

* **Emission**: Gaussian penalty on perpendicular distance and on the compass
  heading difference to each edge.
* **Transition**: requires road-network connectivity between consecutive
  candidate edges; adds a penalty proportional to the mismatch between the
  observed movement and the straight-line candidate distance (a vehicle cannot
  teleport across disconnected roads).
* Returns a `MapMatchResult` with per-pose matched `RoadCandidate`s and the
  Viterbi posterior.

`HMMPose` bundles an ENU pose, heading and timestamp; `HMMMatcher.pose_from_state`
converts an engine `NavigationState`.

### `map_loader.py`
Reads GeoJSON (LineString / MultiLineString / Feature / FeatureCollection),
converts WGS84 polylines to the local ENU frame at a given origin, and builds a
`RoadGraph`:
* `polylines_from_geojson(geojson)`
* `polylines_to_enu(polylines_lonlat, origin_lat, origin_lon)`
* `load_road_graph(source_path=..., geojson=..., origin_latitude=..., origin_longitude=...)`
* `load_road_graph_from_polylines(polylines_enu)`

### `map_matcher.py` (facade)
The engine-facing surface:
* `match(east, north, heading, candidates=None)` — nearest plausible road;
  candidates are generated from the owned graph when omitted.
* `match_sequence(poses)` — HMM Viterbi decode (requires a graph).
* Constructor accepts HMM + candidate-generation tuning parameters.

`RoadCandidate` is defined in `road_candidate.py` and re-exported.

## Integration

In `IDREngine.update_map_match` the matched pose is applied via
`GNSSINSFusion.re_localize(east, north, std_m)` (`map_match_std_m`,
default 3 m). This is a hard correction relative to GNSS, so it should only be
enabled when a road network is actually available (`navigation_config.yaml`,
`map_matching.enabled`).

## Tests

```bash
env\Scripts\python.exe -m pytest tests/map_matching -q
```