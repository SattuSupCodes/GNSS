# Sensor Fusion (D-S3 / D-S4 / D-S6)

This document describes the GNSS + INS fusion backend delivered by the Phase 1
navigation team. All code lives under `src/navigation/fusion/` and is consumed
by the `IDREngine` facade (`src/navigation/engine/idr_engine.py`).

## Conventions

* **World frame**: local ENU (`x` East, `y` North, `z` Up), origin fixed at the
  first GNSS fix (see `LocalENU` in `core/math_utils.py`).
* **Heading**: compass bearing, clockwise from **North**. `0` = North,
  `+pi/2` = East, `pi` = South, `-pi/2` = West.
* **Gyro sign**: a positive `gyro_z` is counter-clockwise about Up (a left
  turn), so compass heading *decreases* when `gyro_z` is positive:
  `heading_new = heading - (gyro_z - bias) * dt`.

## Filter state (8-D)

```
x = [east, north, v_east, v_north, heading, gyro_bias,
     accel_bias_east, accel_bias_north]
```

* Positions/velocities in metres / m/s in the local ENU frame.
* Heading in radians (compass convention above).
* Biases are additive corrections applied before integration.

State indices, the discrete-time constant-acceleration `motion_model`,
`process_noise(dt)` and `default_covariance()` are shared by the EKF and the
UKF and live in `fusion/state_model.py`.

## Filters

Both filters expose the *identical* method surface, which is why the rest of
the backend never cares which one is instantiated:

| Method | Purpose |
|---|---|
| `predict(accel_enu, gyro_z, dt)` | propagate INS (prediction) |
| `update_gnss_position(e, n, acc)` | GNSS position fix |
| `update_speed(speed, std)` | speed pseudo-measurement (GNSS or AI) |
| `update_heading(heading, std)` | heading pseudo-measurement (GNSS/compass/AI) |
| `update_accel_correction(corr, std)` | AI accel-bias correction (D-S7) |
| `to_state(t)` / `position_std_m` / `speed_mps` / `heading_rad` | output |

### EKF (`ekf.py`)
Propagates the mean and covariance through a **numerical Jacobian** of the
motion model. Speed updates are linearised (`||v||` gradient), with a rest
branch that projects the speed along the current heading so velocity can be
initialised from standstill. Uses Joseph-form covariance for numerical safety.

### UKF (`ukf.py`)
Scaled unscented transform (`alpha=1.0, beta=2.0, kappa=0.0`) with 17 sigma
points. Heading is handled as a periodic component: a circular weighted mean,
wrapped deviations, and wrapped innovations. The UKF does **not** linearise the
motion model or the nonlinear `||v||` speed measurement, at a modest compute
cost. No third-party filter library is required (numpy only).

### Choosing a filter
`GNSSINSFusion(filter_factory=EKF)` selects the implementation. Both are
validated to track the same scenario in `tests/fusion/test_ukf.py`
(`test_ukf_matches_ekf_on_linear_scenario`).

## Fusion orchestrator (`gnss_ins_fusion.py`)

`GNSSINSFusion` owns the filter, the GNSS health machine and the ENU origin:

* `predict_imu(accel_enu, gyro_z, dt, timestamp)` — INS prediction; also calls
  `health.check_stale` so the mode flips to `DEAD_RECKONING` when the GNSS feed
  goes silent mid-trip.
* `update_gnss(lat, lon, accuracy, timestamp, speed, heading)` — converts to
  ENU, runs the health machine, applies the fix (plus optional speed/heading).
  Returns `(mode, accepted, innovation_m)`.
* `update_ml(...)` — feeds AI velocity/heading/accel corrections (D-S7).
* `apply_lateral_constraint()` / `apply_zupt()` — vehicle constraints (D-S9).
* `re_localize(east, north, std)` — hard external correction (e.g. a reliable
  map-matched pose).

### Soft re-localization
After an outage the position error can be far larger than the reported GNSS
accuracy. During `RECOVERING` the measurement uncertainty is inflated to
`max(accuracy, re_localize_inflation * innovation)`, so the first fixes pull
the filter toward the track without over-trusting a single glitchy fix.

## Modes

The engine-facing mode strings are:

```
UNINITIALIZED | GNSS_INS_FUSION | GNSS_INS_DEGRADED | RECOVERING | DEAD_RECKONING
```

Mapping from the health machine (`GNSSMode`): `HEALTHY -> GNSS_INS_FUSION`,
`DEGRADED -> GNSS_INS_DEGRADED`, `RECOVERING -> RECOVERING`,
`UNAVAILABLE -> DEAD_RECKONING`.

## Tests

`env\Scripts\python.exe -m pytest tests/fusion -q`
