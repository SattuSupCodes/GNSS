# ML Models (Navigation workstream)

Learned components that improve the INS/GNSS navigation engine when GNSS is
unavailable or degraded. Models are trained **offline** on recorded vehicle
trips and applied **at runtime** to smartphone-only sensor streams. This
document describes what each model does, how it is trained, how it is wired,
and its measured performance.

## Model inventory

| Model | Kind | Input | Output | Artifact | Test metrics |
|---|---:|---|---|---|---|
| D-T2 speed | LSTM / GRU / TCN | 100-sample, 9-channel calibrated IMU (`*_cal`) | vehicle speed (m/s) + std | `models/speed_{lstm,gru,tcn}.pt` | see `speed_model_evaluation.md` |
| D-T3 vibration | Random Forest (300 trees) | 100-sample, 6-channel IMU (`accel_x..gyro_z`) | `normal / vibration / stationary` | `models/vibration_classifier.joblib` | acc 0.9568, F1 0.9491 |
| D-T4 IMU correction | Random Forest (300 trees) | 100-sample, 6-channel IMU | forward accel error (m/s²), rotated to ENU | `models/imu_correction.joblib` | RMSE 0.2355 m/s², MAE 0.1319 |
| D-T5 error model | Random Forest (300 trees) | 100-sample, 6-channel IMU + current speed | drift rate (m/s) | `models/error_model.joblib` | RMSE 4.889 m/s, MAE 3.492 |

All Random Forest artifacts were trained per-trip (trip-level splits,
`seed=2024`), features engineered in `src/models/ml_common.py`, and inference
kept on the serial path (`n_jobs=1`) to avoid joblib's ~40 ms lock-sleep on
single-row predictions.

## Runtime wiring

The D-T3 / D-T4 / D-T5 adapters implement the contracts defined in
`src/navigation/engine/model_interface.py` and are combined through
`TrainedMLInference`:

```
idr_engine (IDREngine)
        <-update_ml(MLNavigationOutput)-
TrainedMLInference.evaluate(timestamp, window)      (1, 100, 6) @ ~1 Hz
        |                                        |
        +--> D-T3 RandomForestVibrationClassifier
        |        `stationary` -> speed_mps = 0 (tight std)
        |        `vibration`  -> accel-correction std x2
        +--> D-T4 RandomForestIMUCorrectionModel
        |        forward error rotated to ENU with engine heading
        +--> D-T5 RandomForestErrorModel
                 position_error_m = drift_rate * gnss_age (finite, >=0)
```

- Windows are accumulated from the **base** calibrated IMU columns
  (`accel_x .. gyro_z`) — the same channel layout the models were trained on.
- Live engine state (heading, speed, GNSS age) is injected through providers
  bound by `TrainedMLInference.bind(...)` in `engine_trip_runner.run_trip`.
  None of these providers leak reference/GNSS *truth*; they read the engine's
  own estimate.
- `MLNavigationOutput` fields flow into `IDREngine.update_ml`:
  D-T4 -> `EKF.update_accel_correction`, D-T5 -> a non-negative error floor
  that raises the reported `position_error_m` (never lowers it), which in turn
  shapes `confidence` (D-S10).
- **Fallback is preserved.** If an artifact is missing or an adapter raises,
  that field is simply omitted; `fallback` returns no corrections and the
  engine runs classically. The two integration paths are independent:
  `CompositeMLInference` (D-T2 speed, 9-channel `*_cal` windows, config-driven)
  and `TrainedMLInference` (D-T3/4/5, 6-channel windows, parameter-driven, used
  by `scripts/evaluate_blackout_ml.py`).

## Blackout validation

`scripts/create_blackouts.py` generates deterministic GNSS-outage scenarios
(config `configs/evaluation_config.yaml`, seed 2024, durations 5..120 s).
`scripts/evaluate_blackout_ml.py` then re-runs each scenario three ways —
clean (full GNSS), baseline (outage, no ML), and ML (outage with D-T3/4/5) —
and reports RMSE / final error / confidence / predicted error per scenario and
as aggregates in `models/blackout_ml_validation.json`.

> **Scope note:** the repository currently contains calibrated data for only
> `trip_m`, `trip_s1`, `trip_s2`; the 34-scenario validation the project
> originally produced is therefore **not reproducible**. The committed
> artifacts and validation runs cover the 18 scenarios realizable on these
> trips (6 of them on the held-out test-split trip `trip_m`). Aggregate numbers
> reported from the current run are computed **only over these available
> scenarios** and should be read with that scope in mind.

### D-T5 activity

The D-T5 learned error floor (`position_error_m = drift_rate * gnss_age`) is
now demonstrably active during outages:

- predicted error is finite and non-negative throughout a blackout
  (`ml_pred_err_blackout_m` in the report),
- observed `ml_error_active_ratio` in the latest run is > 0.9 (the floor was
  actively raised on the large majority of blackout rows),
- a regression guard asserts `position_error_m` stays finite even when the
  floor is 0/`inf`/`nan` (see `tests/ml`).

## Limitations

- The Random Forest artifacts were pickled with scikit-learn 1.9.0; loading
  with the local 1.7.x emits an `InconsistentVersionWarning` (predictions
  remain valid).
- Vibration labels use the 3-class scheme (`normal`, `vibration`,
  `stationary`); the protocol docstring in `model_interface.py` also lists a
  5-class text scheme that is aspirational, not trained.
- D-T5 error growth is a linear `drift * age` approximation; it is an error
  floor for confidence, not a trajectory correction.