# GNSS / INS navigation engine — API reference

Entry points for offline evaluation and the exposed runtime surface.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/run_trip.py` | Run the navigation engine over a trip dataframe (drives `run_trip`) |
| `scripts/evaluate.py` | Re-load every speed/ML artifact and produce `models/speed_model_comparison.csv` |
| `scripts/train_speed_model.py` | Train LSTM / GRU / TCN speed model (`--model`, `--epochs`) |
| `scripts/train_baselines.py` | Train D-T1 Linear / RF / XGB speed baselines |
| `scripts/evaluate_blackout_ml.py` | Blackout validation (clean / baseline / ML) -> `models/blackout_ml_validation.json` |
| `scripts/create_blackouts.py` | Deterministic GNSS-outage scenario generator (output `data/blackout/`) |
| `scripts/train_vibration_model.py` | Train the D-T3 vibration classifier |
| `scripts/train_correction_model.py` | Train the D-T4 IMU-correction model |

Scripts prepend the repository root to `sys.path` (bootstrap), so they can be
invoked as `python scripts/<name>.py` or `python -m scripts.<name>` from the
repository root.

## Runtime integration

`src/navigation/engine/model_interface.py` is the single contract between the
navigation backend and all learned components:

| Class | Role |
|---|---|
| `SpeedModel` / `VibrationClassifier` / `IMUCorrectionModel` / `ErrorModel` | ABC contracts (D-T2/D-T3/D-T4/D-T5 adapters implement these) |
| `TrainedSpeedModel` | Wraps a LSTM / GRU / TCN checkpoint + scaler |
| `CompositeMLInference` | Config-driven D-T2 integration (9-channel `*_cal` windows) |
| `TrainedMLInference` | D-T3 + D-T4 + D-T5 integration (6-channel windows, `bind(...)` providers) |
| `FallbackMLInference` | No corrections; classical engine behaviour |
| `build_ml_inference(config, repo_root)` | Factory: disabled/missing/unknown -> fallback |

`MLNavigationOutput` (in `src/navigation/interfaces/messages.py`) carries:
`speed_mps`, `speed_std_mps`, `heading_rad`, `heading_std_rad`,
`accel_correction_enu`, `accel_correction_std_mps2`, `position_error_m`.

## Engine surface

`IDREngine` (`src/navigation/engine/idr_engine.py`) is the entry point used by
`run_trip`:

```
update_gnss(GNSSSample)      GNSS fix (init/localize, health, EKF updates)
update_imu(IMUSample)        INS prediction
update_ml(MLNavigationOutput) learned measurements + D-T5 error floor
update_map_match(...)        soft map-matched correction (D-S8)
apply_non_holonomic_constraint() / apply_zupt()
get_state() -> NavigationState
get_state_dict() -> JSON-style state per the D-S11 API spec:
   timestamp, latitude, longitude, velocity, heading, confidence,
   position_error, mode, east_m, north_m, velocity_east_mps, velocity_north_mps
```

Modes emitted: `UNINITIALIZED`, `GNSS_INS_FUSION`, `GNSS_INS_DEGRADED`,
`RECOVERING`, `DEAD_RECKONING`.

## Runner

`run_trip(df, config, engine=None, gnss_enabled=True, ml_inference=None)`
(`src/engine/engine_trip_runner.py`) executes a trip dataframe row by row:

- sorts by `timestamp`, requires a valid `timestamp` column;
- builds an engine (default EKF, NHC + ZUPT on) unless one is provided;
- buffers a 100-sample calibrated IMU window for the D-T2 model (config
  `ml.enabled`) and feeds updates every sample;
- when `ml_inference` is provided (`TrainedMLInference`), additionally runs
  the 6-channel D-T3/4/5 corrections every 100 IMU rows (~1 Hz);
- respects `gnss_available` masking and returns an `EngineTripResult` with the
  full `trajectory` dataframe (reference + reported columns, including
  `position_error` and `confidence`) and metrics (position/velocity/heading
  RMSE, final position error).

### Offline evaluation metrics

`_evaluate` computes error only against explicitly-present `reference_*`
columns (vehicle ground truth, never fed to the runtime). `_safe_rmse` returns
`None` when no valid reference rows exist.