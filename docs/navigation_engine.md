# Navigation Engine (D-S11, D-S7, D-S9)

`IDREngine` (`src/navigation/engine/idr_engine.py`) is the public facade the
rest of the system (offline evaluation scripts, future online service) calls
into. It owns and coordinates all Phase 1 navigation-compilation modules:

| Concern | Owner | Deliverable |
|---|---|---|
| Filter + GNSS health + ENU origin | `GNSSINSFusion` | D-S3 / D-S4 / D-S5 / D-S6 |
| Road-network correction | `MapMatcher` / HMM | D-S8 |
| Confidence / error reporting | `ConfidenceEstimator` / `position_error` | D-S10 |
| AI corrections | `MLInference` adapters | D-S7 |
| Vehicle constraints | `NonHolonomicConstraint` | D-S9 |

## Message inputs

The engine consumes frozen dataclasses from `src/navigation/interfaces/messages.py`:

* `IMUSample(timestamp, accelerometer, gyroscope, ..., linear_acceleration_enu, heading_rad)`
* `GNSSSample(timestamp, latitude, longitude, accuracy, speed, heading)`
* `MLNavigationOutput(timestamp, speed_mps, speed_std_mps, heading_rad, heading_std_rad, accel_correction_enu)`

All headings follow the compass convention (0 = North, clockwise positive).

## Lifecycle

```
engine = IDREngine()                 # defaults: EKF, no map, classical ML
engine.initialize(lat, lon, heading) # or let the first GNSS fix initialise
engine.update_gnss(gnss)             # first fix auto-initialises if needed
```

### Stream updates
* `update_imu(sample)` — predict INS; uses `sample.linear_acceleration_enu`
  if present, otherwise transforms raw accelerometer with the current heading
  via `phone_to_navigation_2d`.
* `update_gnss(sample)` — GNSS fix + optional speed/heading; drives the outage
  state machine.
* `update_ml(output)` — feeds AI measurements (D-S7).

### Constraints & map matching
* `apply_non_holonomic_constraint()` — suppress lateral velocity (D-S9).
* `apply_zupt()` — zero-velocity update when stationary.
* `update_map_match(candidates=None, std_m=None)` — correct the solution to the
  nearest plausible road. Without candidates the configured `MapMatcher` owns a
  road graph and generates them.

### Output
* `get_state()` returns a `NavigationState` (typed dataclass).
* `get_state_dict()` returns a JSON-style dict:

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

## Confidence (D-S10)

`ConfidenceEstimator.estimate(position_error_m, mode, gnss_age_s)`:

```
effective_error = max(position_error, drift_rate * gnss_age)
confidence      = exp(-effective_error / reference_error) * mode_factor
```

* `drift_rate * gnss_age` makes confidence degrade smoothly during an outage
  (dead reckoning), even before the filter covariance finishes growing.
* `mode_factor` boosts `GNSS_INS_FUSION` slightly and damps `DEAD_RECKONING`.
* Scalar errors come from `position_error.py` helpers (position root-variance,
  CEP50/CEP95 radii, probability-radius).

## AI integration (D-S7)

`engine/model_interface.py` defines the *contract* for Tanishk's learned
components (see `docs/` from the ML team for D-T1..D-T10):

* `SpeedModel`, `IMUCorrectionModel`, `ErrorModel`, `VibrationClassifier`
* `MLInference.evaluate(timestamp, window) -> MLNavigationOutput`
* `FallbackMLInference` — returns an empty output so the engine runs classically
  until trained checkpoints are wired in.
* `CompositeMLInference` — wraps delivered sub-models without touching the backend.

## Trip runner & scripts

`src/engine/engine_trip_runner.py` feeds a calibrated (or blackout-scenario)
dataframe through the engine exactly like the online runtime and returns a
trajectory plus reference RMSE metrics:

```bash
python scripts/run_dead_reckoning.py <trip_id>
python scripts/run_fusion.py <trip_id>
python scripts/run_fusion.py <trip_id> --scenario data/blackout/60s/<scenario>.parquet
python scripts/run_map_matching.py <trip_id> --map data/maps/road_network.geojson
```

Configuration is YAML-driven via `load_yaml` (mirrors the teammates' CLI style):

* `configs/navigation_config.yaml` — engine/filter/constraints/map/ML
* `configs/fusion_config.yaml` — filter tuning (noise, inflation)
* `configs/map_matching_config.yaml` — HMM + graph parameters

## Tests

```bash
env\Scripts\python.exe -m pytest tests/navigation -q
```
