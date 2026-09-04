# Preprocessing Pipeline

This document describes the offline preprocessing chain that turns one canonical
trip frame (see `docs/dataset.md`) into a model-ready frame, plus the
smartphone–vehicle synchronization step.

Both stages are configuration-driven
(`configs/preprocessing_config.yaml`) and deterministic.

---

## 1. Per-Trip Pipeline

Single entry point: `src/preprocessing/preprocessing_pipeline.py` →
`PreprocessingPipeline.run(df)`. Input is a canonical smartphone frame from
`io_vnbd_loader.load_smartphone_csv` / `load_smartphone_trip`; output is an
enriched canonical frame of the **same row count** (unless samples were dropped).

Order matters and is fixed:

| # | Step | Module | What it does |
|---|------|--------|--------------|
| 1 | clean | `cleaning` | Drop NaN IMU rows, dedupe/sort timestamps, clamp GNSS lat/lon/speed/accuracy to valid ranges |
| 2 | outlier | `outlier_detection` | Remove IMU spikes (> `imu_spike_sigma` within rolling window); drop rows where implied GNSS speed exceeds `gnss_jump_kmh` |
| 3 | filter | `filtering` | Butterworth low-pass (4th order) on all 12 IMU channels, default cutoff 4 Hz @ 10 Hz |
| 4 | resample | `resampling` | Uniform time grid at `fs` (default 10 Hz); NaN IMU gaps filled with linear interp, GNSS carried by forward-fill hold |
| 5 | normalize | `normalization` | Per-channel z-score of the 12 IMU channels (µ/σ fitted on the same frame) |
| 6 | coords | `coordinate_transforms` | Add local ENU `pos_east_m` / `pos_north_m` / `pos_up_m` from GNSS lat/lon at the trip start |
| 7 | sync | `synchronization.ffill_gnss` | Forward-fill GNSS so every IMU row carries the best-known fix (lat/lon/speed/heading/satellites) |

### Config knobs

`configs/preprocessing_config.yaml` → `PipelineConfig` dataclass:

- `fs` — resample rate (Hz); must match the `sampling_rate_Hz` of the trip.
- `lowpass_cutoff_hz`, `filter_order` — Butterworth parameters; set
  `lowpass_cutoff_hz` to `null` to skip filtering.
- `imu_spike_window`, `imu_spike_sigma` — spike detection.
- `gnss_jump_kmh` — max plausible GNSS speed change between consecutive rows.
- `apply_zscore`, `add_enu`, `ffill_gnss` — stage toggles (bool).

### Output shape

- Row count preserved 1:1 for the nominal 10 Hz stream (verified on `vw16b`:
  1126 in → 1126 out).
- Columns: the 24 canonical smartphone columns + `pos_east_m`, `pos_north_m`,
  `pos_up_m`, `trip_id`, `sync_status`.
- IMU columns are low-passed and z-scored; GNSS columns are raw values
  forward-filled (never interpolated).

---

## 2. Smartphone–Vehicle Synchronization

Goal: put the **reference-only** vehicle stream on the smartphone clock so it can
be used as ground truth offline.

`scripts/synchronize_data.py` per trip:

1. Load smartphone frame (native clock) + raw vehicle CSV.
2. Convert vehicle `Time Since Start of Day (seconds)` to absolute POSIX
   timestamps using the smartphone recording start.
3. `estimate_constant_offset(a=smartphone, b=vehicle, trace=gps_heading)`
   cross-correlates the two heading traces on a common absolute-time grid.
4. **Semantics of the returned `r`:** adding `r` to the **vehicle** timestamps
   aligns the vehicle onto the smartphone,
   `a(t) ≈ b(t + r)`. Verified empirically: for b-timestamps shifted `+1.7 s`,
   the estimator returns `r = -1.7` and applying `b + r` yields MSE 0.
5. The vehicle is resampled onto the smartphone grid `+ r`
   (`synchronize_vehicle_to_grid`, linear interp, GNSS-style cols held).
6. Smartphone is written with forward-filled GNSS only — it is **never shifted**;
   the smartphone clock is the reference.

Outputs under `data/processed/synchronized/`:

- `trip_<id>_smartphone.parquet` — canonical smartphone frame.
- `trip_<id>_vehicle_reference.parquet` — aligned vehicle frame
  (`is_reference=True`).

### Verification

- Synthetic shift test: `tests/preprocessing/test_synchronization.py` asserts the
  estimator returns the exact magnitude and sign of a known `+1.7 s` shift.
- Real `vw16b` smartphone↔vehicle offset is `0.000 s` (clocks already aligned).

---

## 3. Re-running end to end

```bash
# clean + preprocess + ENU + (optionally GNSS ffill) -> trip parquet + splits
python scripts/prepare_dataset.py --trip vw16b          # or --all

# smartphone-native + synchronized vehicle reference parquets
python scripts/synchronize_data.py --trip vw16b          # estimate offset
python scripts/synchronize_data.py --trip vw16b --offset 0.0   # opt-in manual offset
```

Both scripts print row counts / coverage stats. Run `python -m pytest` from the
repo root to validate (all tests use small synthetic fixtures; none require the
real dataset).