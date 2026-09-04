# Phase 2 — Calibration, Alignment and ML-Ready Sequences

Builds on the Phase 1 canonical/processed frame (`docs/dataset.md`,
`docs/preprocessing.md`). Adds a config-driven calibration layer that recovers
**gravity**, **sensor calibration**, **phone orientation** and **phone alignment
(device → world ENU)**, and then slices trips into fixed-length, leakage-safe
**window sequences** for ML/navigation consumers.

Scope guard: this is the data-engineering layer. It deliberately does **not**
implement speed estimation, IMU correction, VDR/fusion, dead reckoning or
map matching — those remain separate sub-projects that consume these outputs.

```
raw S-*.csv (Phase 1) → processed trip (Phase 1) → data/calibrated/
                                                 → data/training|validation|testing/
```

---

## 1. What the Calibration Pipeline Adds

Entry point: `CalibrationPipeline.run(df)` in
`src/calibration/calibration_pipeline.py`, driven by
`configs/calibration_config.yaml`. Every new value lives in its own column;
**raw Phase 1 columns are never modified or dropped.**

| Stage | Module | Columns added |
|-------|--------|---------------|
| Gravity | `gravity_estimation.py` | `gravity_est_x/y/z`, `gravity_est_magnitude`, `linear_accel_x/y/z`, `gravity_est_valid` |
| Sensor calibration | `sensor_calibration.py` | `<accel|gyro|mag>_<x|y|z>_cal` |
| Orientation | `orientation_estimation.py` | `orient_qw/qx/qy/qz`, `orient_roll_deg`, `orient_pitch_deg`, `orient_yaw_deg`, `orient_heading_source`, `orient_heading_quality`, `orient_tilt_quality` |
| Phone alignment | `phone_alignment.py` | `<accel|gyro|mag>_<x|y|z>_aligned` (calibrated device values rotated into ENU) |
| Provenance | pipeline | `category`, `driver` (re-derived from the source path) |

Semantics of each family:
- `gravity_est_*` — the **slow**, mostly low-frequency component of the
  accelerometer (below ~0.05 Hz). `linear_accel_* = accel − gravity_est`.
- `*_cal` — **calibrated device-frame** values: `cal = scale·(raw − bias) + offset`.
  By default the profiles are **configured identity** (copy-through, honest
  "no correction applied"). Real estimation is opt-in (see §4).
- `orient_*` — device attitude: scalar-first quaternion + Euler.
- `*_aligned` — the **calibrated** device-frame values rotated by the alignment
  transform into the world ENU frame. `aligned = align(cal)`, never `align(raw)`.

The pipeline emits a serialisable JSON metadata block (`CalibrationResult.metadata`)
recording status, gravity stats, the exact orientation config, the alignment
convention, per-sensor calibration profiles (with `source`) and `sensor_availability`.

---

## 2. Conventions (explicit, documented, self-consistent)

- **Device frame** (Android accelerometer convention): X = right, Y = up the
  long edge (screen top), Z = out of the screen.
- **World frame**: ENU (East, North, Up).
- **Quaternions** are scalar-first `(w, x, y, z)`, unit norm.
  `quat_rotate(q, v)` rotates a device vector into the world frame.
- **Euler angles** follow `R = Rz(yaw)·Ry(pitch)·Rx(roll)` device → world.
  `orient_yaw_deg` is the rotation **about world Up**, positive CCW viewed from
  above. It is a *rotation angle*, **not** by itself the bearing of the phone's
  top edge — mapping `yaw` to a compass bearing depends on the mount convention
  and is the job of phone alignment (see presets below).
- **GNSS course-over-ground is never treated as phone yaw.** The GNSS heading
  is vehicle course; the phone can be mounted at any angle relative to it.
- Alignment transform: `world = R_alignment · device` (unit quaternion or 3×3
  rotation matrix, both validated utilities in `phone_alignment.py`).

### Alignment presets (`PRESET_CONVENTIONS`)

"TOP_<dir>" names the world direction the phone's top edge (device +Y) points to.

| Preset | yaw | pitch | roll | Meaning |
|--------|-----|-------|------|---------|
| `TOP_NORTH_SCREEN_UP` | 0° | 0° | 0° | Flat, top North (device == ENU) |
| `TOP_EAST_SCREEN_UP` | −90° | 0° | 0° | Flat, top East |
| `TOP_SOUTH_SCREEN_UP` | 180° | 0° | 0° | Flat, top South |
| `TOP_WEST_SCREEN_UP` | 90° | 0° | 0° | Flat, top West |
| `TOP_UP_SCREEN_NORTH` | 180° | 90° | 0° | Upright portrait, screen facing the N/S plane |

There is **no universal mount assumption** — the convention is explicit,
configurable, and recorded in `alignment` metadata so every downstream artifact
knows exactly which transform was applied.

---

## 3. Gravity Estimation Methodology

A phone on a moving vehicle is not static, so gravity cannot be assumed
constant along one axis. Instead:

> gravity ≈ the low-frequency component of specific force.

- **lowpass (default)**: zero-phase Butterworth (`scipy.signal.sosfiltfilt`),
  4th order, cutoff 0.05 Hz. Runs are filtered over **contiguous valid blocks**
  so NaN gaps are never fabricated over.
- **mean**: segment-average fallback for sub-filter-length windows.
- Runs shorter than `min_run` fall back to their mean instead of a NaN wall.

Below `min_samples` finite accel rows the status is `insufficient_samples` and
the columns are NaN — no guessed gravity vector is produced.

---

## 4. Sensor Calibration: estimated vs configured vs unavailable

Every profile is tagged `source ∈ {estimated, configured, unavailable}` and the
tag is carried into metadata so downstream code can tell **estimated** values
from **configured** ones.

| Mode | When | What happens |
|------|------|--------------|
| `configured` (default) | no fit data | Identity model: `raw → raw`. Columns still exist (uniform shape). |
| `est. gyro bias` | rest window detected | Zero-rate bias from the mean of static samples; scale/misalignment out of scope. |
| `est. accel/mag` | opt-in fit | Least-squares sphere (bias) / normalized-ellipsoid (bias + per-axis scale) fits over orientation-diverse samples. |

Utilities (all tested):
- `fit_sphere_ls` — center (bias) of a triaxial sphere, unit scale.
- `fit_ellipsoid_scale_bias` — per-axis scale + bias; the global magnitude
  factor is **not** identifiable and is normalised to `scale_x = 1`
  (fine for shape correction, not absolute magnitude; recorded in the profile note).
- `estimate_gyro_bias` — static-mean zero-rate bias.

`scripts/calibrate_dataset.py` detects a near-rest block
(`data/processed/...`, accel magnitude ∈ [9.3, 10.3] AND gyro magnitude < 0.3
for ≥ 3 s) to estimate gyro bias; motorway data with orientation diversity can
additionally enable `--fit-accel` / `--fit-mag`.

---

## 5. Orientation Estimation

A practical complementary filter (`OrientationEstimator`), not an INS-grade
filter:

- **roll/pitch** from the low-frequency gravity vector.
- **yaw** from the tilt-compensated magnetometer when the field magnitude lies in
  the Earth-field band (20–70 µT, `magnetometer_quality`), otherwise integrated
  from the gyroscope (drifting).
- Per-sample `orient_heading_source` (`magnetometer` / `gyro`) and
  `orient_heading_quality` (`high` / `medium` / `low` / `unavailable`) say
  *which* estimate held for each sample instead of pretending every heading is
  trustworthy.

---

## 6. Sequences (ML-ready windows) — leakage policy

`scripts/generate_sequences.py` slices calibrated trips into fixed-length
windows (`src/data/sequence_generator.py`). Hard rules:

- **Per-trip generation**: windows are built trip by trip; a window can never
  cross a trip boundary.
- **Trip-level splits only**: generation uses the Phase 1 split lists
  (`data/splits/{train,validation,test}_trips.txt`, 50/11/11). Each trip belongs
  to exactly one split, so every window inherits its trip's split and no trip id
  appears in two splits. Random row-level splitting is forbidden.
- **Fixed length**: default 100 rows (10 s @ 10 Hz), stride 100 (non-overlapping).
  Incomplete tails are dropped (or kept via `drop_incomplete_tail: false`).
- **Reproducible provenance**: every row carries `sequence_id`, `trip_id`,
  `split`, `window_index`, `window_start_timestamp`, `window_stop_timestamp`,
  `sample_in_window`; each `sequence_id` group is exactly `window_rows` long.

Outputs: `data/training/sequences.parquet`, `data/validation/sequences.parquet`,
`data/testing/sequences.parquet` (long format, group by `sequence_id`), plus
`data/sequences_metadata.json`. All generated data is git-ignored.

---

## 7. Usage

```bash
# 1) calibrate all trips (or --trip vw16b)
python scripts/calibrate_dataset.py

# 2) build fixed-length windows per Phase 1 split
python scripts/generate_sequences.py
python scripts/generate_sequences.py --window-rows 200 --stride-rows 100
```

Python API (`DatasetManager`):

```python
from src.data.dataset_manager import DatasetManager
dm = DatasetManager("data/raw", "data/processed")
df = dm.load_calibrated_trip("vw16b")   # calibrated/aligned frame (or runs pipeline in memory)
train = dm.load_split("train")          # long-format window frame
```

---

## 8. Scientific Rules Honoured

1. Raw acceleration is never overwritten (`accel_*` stays byte-identical).
2. No fabricated/missing data: NaN gaps propagate; `_valid` flags mark validity.
3. Smartphone-generated values are clearly separated from reference GNSS/vehicle
   fields (`*_est`, `*_cal`, `*_aligned`, `orient_*`).
4. GNSS course ≠ phone yaw; orientation conventions are explicit and recorded.
5. No universal mount assumption: presets + custom Euler angles, kept in metadata.
6. No train/validation/test leakage (see §6).
7. Backward compatible: every Phase 1 column and test still passes unchanged.

## 9. Known Limitations

- Complementary filter yaw drifts when the magnetometer is unusable (gyro-only).
- `fit_ellipsoid_scale_bias` cannot recover absolute magnitude (scale_x normalized).
- Alignment is a fixed static convention per run; a running estimate of the
  momentary mount angle (e.g. from the first straight segment) is explicitly out
  of phase-2 scope and left to the navigation sub-project.
- Sensor calibration estimation requires orientation diversity (driving) or a
  clean rest block; an idling motorway trip may legitimately stay "configured".