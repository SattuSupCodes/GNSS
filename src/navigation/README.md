# `src/navigation` — Intelligent Dead Reckoning Phase 1 Backend

This package is the compile-time navigation backend for the SIH 2024
**Intelligent Dead Reckoning** problem: it fuses vehicle GNSS, phone IMU and
(optionally) AI/ML estimates into one continuous, outage-tolerant position
solution.

It is a cooperation of several teammates' deliverables (D-S1…D-S11 from the
Phase 1 plan). This README explains **what each piece does, what was changed
during this work, why, and how to use it** — read it first if you are new to
this part of the repo.

> Authors note: the folder is called "navigation" but it is the **whole backend
> not just INS** — fusion, health, constraints, confidence, map matching and
> the engine facade all live here. Keep it that way; the separate `src/engine`
> folder holds only *trip evaluation / CLI* glue.

---

## 1. Quick start

```bash
# from the repo root (C:\Projects\GNSS)
env\Scripts\python.exe -m pytest tests src\navigation\tests -q   # 259 tests, all green

# run a trip through the fused engine + RMSE report
env\Scripts\python.exe scripts\run_fusion.py s1

# dead-reckon through a GNSS blackout scenario
env\Scripts\python.exe scripts\run_fusion.py s1 --scenario data\blackout\60s\<scenario>.parquet

# map-match a trip (needs a GeoJSON road network)
env\Scripts\python.exe scripts\run_map_matching.py s1 --map data\maps\road_network.geojson
```

Environment: Python 3.11 (venv `env\Scripts\python.exe`), numpy, scipy, pandas,
pyyaml, pytest. **No third-party filter/networkx/ML frameworks required** — the
EKF/UKF and road graph are pure numpy/standard-lib. ML weights get wired later
(see §8).

---

## 2. Conventions (REALLY important)

Every decision in this package hangs off a set of conventions. They match the
induction / dataset conventions and are asserted in tests. **Do not mix frames.**

| Concept | Convention |
|---|---|
| World frame | local **ENU** (`x` = East, `y` = North, `z` = Up), origin = first GNSS fix |
| Heading | **compass, clockwise from North**: 0 = North, `+pi/2` = East, `pi` = South, `-pi/2` = West |
| Gyro sign | positive `gyro_z` = counter-clockwise about Up (left turn) ⇒ **heading decreases**: `heading_new = heading - (gyro_z - bias) * dt` |
| Device frame | phone +X forward / +Y left / +Z up (**default** alignment); override with `forward_device` in `phone_to_navigation_2d` |
| Constants | `EARTH_RADIUS_M = 6_371_000`, `DEG2RAD = pi/180` in `core/math_utils.py` |

### Why the heading convention matters (history)
The original D-S2 baseline used `quat_to_euler(...)["yaw"]` which is a
**CCW-from-East** angle. The three sub-deliverables historically disagreed on
the sign — which silently produced a mirrored track. As part of this work:

* `src/engine/ds2_runner.py` now uses `heading_compass_from_quaternion`.
* `src/engine/ds2_evaluation.py` now compares against `np.radians(gps_bearing_deg)`
  instead of `90 - bearing`.

Copied into anything new: ungolfed quaternion/Euler helpers live in
`core/math_utils.py`.

---

## 3. Package layout (what sits where)

```
src/navigation/
├── __init__.py              # public exports (the "API surface" of the package)
├── adapters/
│   └── aaqib_data.py        # pandas DataFrame -> IMU/GNSS Sample (Aaqib's calibrated feed)
├── confidence/              # D-S10 — error metrics + knowledge-aware confidence
│   ├── position_error.py    #   scalar error helpers (root-variance, CEP50/95, P-radius)
│   └── confidence.py        #   ConfidenceEstimator (outage-aware [0,1] confidence)
├── constraints/             # D-S9 — vehicle motion constraints
│   └── non_holonomic.py     #   lateral-velocity suppression + ZUPT (stationary detect)
├── core/                    # shared math & low-level transforms
│   ├── math_utils.py        #   ENU conversion, LL<->ENU, wrap_angle, compass helpers
│   ├── sensor_transform.py  #   device->ENU linear acceleration transform
│   └── sensor_adapter.py    #   legacy osc/pickle adapter (kept for D-S2/older tools)
├── engine/                  # D-S7 + D-S11 — public facade of the whole backend
│   ├── idr_engine.py        #   IDREngine: initialize/update_imu/update_gnss/update_ml/...
│   └── model_interface.py   #   AI contract: SpeedModel, MLInference, Fallback, Composite
├── fusion/                  # D-S3/D-S4/D-S6 — the filter core
│   ├── state_model.py       #   8-D state vector, motion_model, process_noise, covariance
│   ├── ekf.py               #   Extended Kalman filter (numerical Jacobian, Joseph form)
│   ├── ukf.py               #   Sigma-point / scaled unscented Kalman filter
│   └── gnss_ins_fusion.py   #   GNSSINSFusion: filter + health machine + ENU origin + modes
├── health/
│   └── gnss_health.py       # D-S5 — GNSS state machine (HEALTHY/DEGRADED/UNAVAILABLE/RECOVERING)
├── ins/                     # inertial nav helpers (legacy + orientation)
│   ├── ins.py               #   simple integration / legacy bits
│   └── orientation.py       #   OrientationEstimator (device-frame heading integrator)
├── interfaces/
│   └── messages.py          # frozen dataclasses: IMUSample, GNSSSample, MLNavigationOutput, ...
├── map_matching/            # D-S8 — constrain the solution to the road network
│   ├── road_graph.py        #   RoadNode/RoadEdge/RoadGraph + Dijkstra
│   ├── road_candidate.py    #   RoadCandidate (leaf module; avoids circular imports)
│   ├── candidate_generation.py # project position -> nearest road points
│   ├── hmm_matcher.py       #   Viterbi over emitted candidates + connectivity
│   ├── map_loader.py        #   GeoJSON polylines -> ENU polylines -> RoadGraph
│   └── map_matcher.py       #   facade: match(), match_sequence()
└── tests/                   # legacy smoke tests (kept green)
```

Files marked **legacy** (`core/sensor_adapter.py`, `ins/ins.py`) were touched
only to fix imports so they still run; the modern stack is fusion + engine.

---

## 4. The filter core (D-S3/D-S4/D-S6)

### State vector (8-D)

```
x = [east, north, v_east, v_north, heading, gyro_bias,
     accel_bias_east, accel_bias_north]
```

* positions / velocities in **local ENU metres**,
* heading in **compass radians**,
* biases are additive corrections subtracted during integration
  (`gyro_z - gyro_bias`, `accel - accel_bias`).

### Shared model (`fusion/state_model.py`)
`motion_model`, `process_noise(dt)` and `default_covariance()` are the single
source of truth for **both** filters. Discrete-time constant-acceleration
update; `ANGLE_INDICES = (4,)` for angular wrapping. Changing the model in one
place changes both filters — don't fork them.

### EKF (`fusion/ekf.py`)
* `predict(accel_enu, gyro_z, dt)` propagates the mean through the true
  nonlinear model and the covariance through a **numerical Jacobian**, so the
  filter stays correct if `motion_model` is edited.
* `update_gnss_position(e, n, acc)` position fix;
  `update_speed(speed, std)` (with a standstill branch that projects speed
  along current heading so velocity can boot from zero);
  `update_heading(heading, std)`; `update_accel_correction(corr, std)` (AI).
* Joseph-form covariance for numerical safety.
* Output accessors: `to_state(t)`, `position_std_m()`, `speed_mps()`,
  `heading_rad()`, `position_std_isotropic_m()`.

### UKF (`fusion/ukf.py`)
* Scaled unscented transform (`alpha=1.0, beta=2.0, kappa=0.0`), 17 sigma
  points, numpy-only (no filterpy).
* Heading handled as a **periodic** component: circular weighted mean, wrapped
  deviations and wrapped innovations for the measurement update.
* No Jacobians needed → handles the nonlinear `||v||` speed model exactly.

Both filters expose the **same method surface**, so
`GNSSINSFusion(filter_factory=...)` and the engine never care which one is used.
`tests/fusion/test_ukf.py::test_ukf_matches_ekf_on_linear_scenario` proves they
track the same scenario within tolerance.

### GNSSINSFusion (`fusion/gnss_ins_fusion.py`)
Orchestrates one filter instance + the health machine + ENU origin:

* `predict_imu(accel_enu, gyro_z, dt, timestamp)` — INS prediction; kicks the
  health machine so the mode flips to `DEAD_RECKONING` on a silent feed.
* `update_gnss(lat, lon, accuracy, timestamp, speed=None, heading=None)` —
  ENU conversion, health update, position fix (+ optional velocity/heading),
  returns `(mode, accepted, innovation_m)`.
* `re_localize(east, north, std)` — hard external correction (map matching,
  RTK fix, …).
* **Soft re-localization** during `RECOVERING`: measurement uncertainty is
  inflated to `max(accuracy, re_localize_inflation * innovation)`, so the first
  fixes pull the filter onto the track without trusting one glitchy sample.
* Default filter = **EKF**; pass `filter_factory=UKF` for the sigma-point path.

### Mode strings handed back to the engine

```
UNINITIALIZED | GNSS_INS_FUSION | GNSS_INS_DEGRADED | RECOVERING | DEAD_RECKONING
```

(from `GNSSMode`: HEALTHY → `GNSS_INS_FUSION`, DEGRADED → `GNSS_INS_DEGRADED`,
RECOVERING → `RECOVERING`, UNAVAILABLE → `DEAD_RECKONING`).

---

## 5. Confidence & health (D-S10, D-S5)

### GNSS health machine (`health/gnss_health.py`)
Tracks freshness of fixes:
* `HEALTHY` → `DEGRADED` (fixes sparse / accuracy poor) → `UNAVAILABLE`
  (timeout exceeded);
* `RECOVERING` requires a few consecutive good fixes before returning to
  `HEALTHY` (hysteresis, so a single glitch doesn't flip back).
* `check_stale(now)` at every IMU predict → `DEAD_RECKONING` mode.

### Confidence (`confidence/`)
* `position_error.py` — scalar error estimates from covariance: `position_std_m`
  (`sqrt(tr P_2d)`), isotropic mean sigma, CEP50/CEP95 radii, radius-for-a-
  probability.
* `confidence.py` — `ConfidenceEstimator.estimate(position_error_m, mode,
  gnss_age_s)`:

  ```
  effective_error = max(position_error, drift_rate * gnss_age)   # degrades in outage
  confidence      = exp(-effective_error / reference_error)      # maps to [0,1]
  confidence     *= mode_factor                                  # damp DEAD_RECKONING
  ```

  The outage term is what makes confidence fall **during** dead reckoning even
  before the covariance has fully grown. Tuned via `navigation_config.yaml`.

---

## 6. Map matching (D-S8)

The subsystem that snaps the fused solution onto the road network.

```
Estimated pose ──► candidate_generation  ──► HMM (Viterbi)  ──► matched pose
                      (nearest edges)         (emission +          ──► engine
                       within radius)          connectivity)          re_localize
```

* **`road_graph.py`** — minimal directed graph (`RoadNode`, `RoadEdge` with
  length + compass heading, `Dijkstra.shortest_path_length`). `from_polylines`
  builds it from coordinate lists; no networkx required.
* **`candidate_generation.py`** — `generate_candidates(graph, east, north,
  radius_m, max_candidates, heading)`: projects the pose onto nearby edges,
  returns sorted `RoadCandidate`s (road id, projected point, edge heading,
  perpendicular distance).
* **`hmm_matcher.py`** — Viterbi over the pose history: emission penalises
  perpendicular distance + compass heading difference; transition requires
  road connectivity (Dijkstra) and penalises observed-vs-candidate movement
  mismatch. Returns `MapMatchResult` (matched candidate per pose + posterior).
  `HMMPose.pose_from_state` converts a `NavigationState`.
* **`map_loader.py`** — GeoJSON (LineString/MultiLineString/Feature/
  FeatureCollection) → WGS84 polylines → ENU polylines → `RoadGraph`.
* **`map_matcher.py`** — facade the engine calls: `match(east, north, heading,
  candidates=None)` (auto-generates candidates from the owned graph) and
  `match_sequence(poses)` (HMM over a whole trip).
* **`road_candidate.py`** — `RoadCandidate` is defined in its own leaf module
  so `map_matcher` / `candidate_generation` / engine can all import it without
  a circular-import cycle. **Keep it a leaf.**

Integration: `IDREngine.update_map_match(candidates=None, std_m=None)` feeds the
matched pose into `GNSSINSFusion.re_localize(..., map_match_std_m)` (default 3 m).
Map matching is a **hard** correction vs GNSS — keep it behind
`map_matching.enabled` until a real network file is wired.

---

## 7. The engine facade (D-S11) & how to drive it

`engine/idr_engine.py` → `IDREngine` is THE public API. Evaluation scripts and
the (future) online service talk only to this class.

```python
from src.navigation import IDREngine
from src.navigation.interfaces.messages import IMUSample, GNSSSample, MLNavigationOutput

engine = IDREngine()                       # defaults: EKF, no map, classical ML
engine.initialize(lat, lon, heading)       # first GNSS fix auto-initialises too

engine.update_imu(imu_sample)              # IMU at ~10 Hz
engine.update_gnss(gnss_sample)            # GNSS at ~1 Hz (+ optional speed/heading)
engine.update_ml(ml_output)                # AI corrections when available (D-S7)

engine.apply_non_holonomic_constraint()    # vehicle lateral constraint (D-S9)
engine.apply_zupt()                        # zero-velocity update when stationary
engine.update_map_match(candidates=cands)  # or let the owned MapMatcher generate them

state = engine.get_state()                 # typed NavigationState
dct   = engine.get_state_dict()            # JSON-style dict
```

### Input messages (`interfaces/messages.py`, frozen dataclasses)
* `IMUSample(timestamp, accelerometer, gyroscope, ..., linear_acceleration_enu,
  heading_rad)` — prefer `linear_acceleration_enu` when the upstream layer
  (Aaqib's adapter, D-S1) already provides it; otherwise the engine transforms
  raw accelerometer with current heading via `phone_to_navigation_2d`.
* `GNSSSample(timestamp, latitude, longitude, accuracy, speed, heading)`.
* `MLNavigationOutput(timestamp, speed_mps, speed_std_mps, heading_rad,
  heading_std_rad, accel_correction_enu)`.

### Output schema (`get_state_dict`)
```json
{
  "timestamp": 0.0, "latitude": 52.5, "longitude": -1.9,
  "velocity": 4.5, "heading": 0.3,
  "confidence": 0.92, "position_error": 3.1,
  "mode": "GNSS_INS_FUSION",
  "east_m": 12.3, "north_m": 4.5,
  "velocity_east_mps": 0.4, "velocity_north_mps": 4.48
}
```

`NavigationState` has **no** `speed_mps` field — compute
`hypot(velocity_east_mps, velocity_north_mps)` if you need the scalar.

### Trip runner & config glue
`src/engine/engine_trip_runner.py` replays a calibrated (or blackout-scenario)
dataframe through the engine exactly like the online runtime and returns a
trajectory + **reference RMSE** metrics:

* `configs/navigation_config.yaml` — engine/filter/constraints/map/ML switches
* `configs/fusion_config.yaml` — filter tuning (noise, `re_localize_inflation`)
* `configs/map_matching_config.yaml` — HMM + graph parameters
* scripts: `run_dead_reckoning.py`, `run_fusion.py`, `run_map_matching.py`

---

## 8. AI/ML integration (D-S7) — work in progress, by design

`engine/model_interface.py` defines the **contract** Tanishk's learned
components (D-T1…D-T10, produced by the ML team) must satisfy:

* `SpeedModel(speed, accel, heading, window) -> float`
* `IMUCorrectionModel(...)`, `ErrorModel(...)`, `VibrationClassifier(...)`
* `MLInference.evaluate(timestamp, window) -> MLNavigationOutput`
* `FallbackMLInference` → no-op (returns an "empty" output). **This is what the
  engine runs today**, so the entire backend works classically while the
  checkpoints are being trained.
* `CompositeMLInference` — wraps whichever sub-models are delivered (best, RNN,
  transformer…), without touching the backend.

**What this means for the repo now:** the backend is 100% runnable without ML.
When the ML runtime lands, you only need to (a) implement `MLInference.evaluate`
on the trained checkpoints, (b) construct `CompositeMLInference`, and
(c) drop it into `navigation_config.yaml`. `update_ml` already exists and is
covered by tests. The full machine-oriented API document (`docs/api.md`) is
intentionally deferred until that runtime is a real object — the *interface* is
already fixed in `model_interface.py`, so no rework is expected.

---

## 9. What was changed / added in this pass (changelog)

* **Fusion core added**: `fusion/state_model.py`, `fusion/ekf.py`,
  `fusion/ukf.py`, `fusion/gnss_ins_fusion.py` (D-S3/D-S4/D-S6).
* **New modules**: `health/gnss_health.py`, `constraints/non_holonomic.py`,
  `confidence/position_error.py`, `confidence/confidence.py`, `engine/
  model_interface.py`, `engine/idr_engine.py`, full `map_matching/` tree,
  `interfaces/messages.py`, `core/sensor_transform.py`.
* **Heading convention aligned** (bugfix): `src/engine/ds2_runner.py` +
  `src/engine/ds2_evaluation.py` (`heading_compass_from_quaternion`, direct
  `radians(bearing)` reference). See §2.
* **Import fixes** on legacy files (`ins/ins.py`, `core/sensor_adapter.py`,
  `orientation.py`) so old D-S1/D-S2 tooling still runs on the new structure.
* **Circular dependency solved**: `RoadCandidate` moved to `road_candidate.py`
  leaf module (re-exported by `map_matcher.py` for compatibility).
* **UKF bug fixed**: sigma-point state arrays are 2-D; `wrap_state_angles` now
  vectorises instead of assuming a 1-D mean-only array.
* **Trip runner + glue**: `src/engine/engine_trip_runner.py`, 3 YAML configs,
  3 CLI scripts (see §7).
* **docs/**: `sensor_fusion.md`, `navigation_engine.md`, `map_matching.md`
  (team-facing); this README for the package itself.

## 10. Testing

* **Test modules (if you extend, put tests here):**
  `tests/fusion/` (`test_ekf.py`, `test_ukf.py`, `test_gnss_ins.py`),
  `tests/navigation/` (`test_ins.py`, `test_dead_reckoning.py`,
  `test_navigation_engine.py`), `tests/map_matching/` (`test_map_loader.py`,
  `test_hmm_matcher.py`, `test_constraints.py`); plus legacy
  `src/navigation/tests/`.
* Full suite: `env\Scripts\python.exe -m pytest tests src\navigation\tests -q`
  → **259 passed**.
* The tests encode the conventions (§2), EKF↔UKF parity, outage/blackout
  modes, confidence monotonicity, map-loader parsing and constraint
  behaviour. If a test "fights" you, first re-read the convention table.

## 11. Known caveats / next steps

* Map matching requires a real GeoJSON network + map config to be end-to-end
  exercised on data; the geometry/HMM layer is unit-tested only.
* ZUPT/lateral constraints are applied on demand — the trip runner doesn't
  enable them by default yet; decide trigger policy when real-trip dynamics are
  measured.
* ML weights not yet present — §8 is the integration guide.
* `docs/api.md` is deliberately deferred (see §8); this README + §7 are the
  current contract.