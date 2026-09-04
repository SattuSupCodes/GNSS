# Phase 3 - GNSS Blackout Simulation & Evaluation Data

Phase 3 turns the Phase 2 calibrated trips into **GNSS-denied evaluation data**:
for a chosen outage duration, all GNSS runtime fields are masked to `NaN` inside
a real-time window while the IMU, calibrated/aligned sensors, timestamps, ids
and the offline vehicle reference stay **untouched**. The result is exactly what
Tanishk's ML models and Shatakshi's navigation/fusion code should consume to test
position, heading and speed estimation during GPS outages.

```
│  data/calibrated/trip_<id>.parquet        (Phase 2 output)
│        │
│        ▼  scripts/create_blackouts.py
│  data/blackout/<duration>s/<scenario_id>.parquet      (Phase 3 output)
│        scenario: GNSS nan, gnss_available, blackout_phase, reference_*
```

This document is the interface contract for both teammates. It is **data
engineering only** - no navigation model is implemented here.

---

## 1. Rationale

- Real-world GNSS drops out for tens of seconds in tunnels, urban canyons and
  under bridges. The team needs offline datasets that reproduce exactly that
  condition so dead-reckoning/fusion quality can be measured.
- Every artifact is **reproducible**: interval placement is seeded and derived
  from a stable hash of `(global_seed, trip, duration, scenario_index)`.
- Generated data is **honest**: an outage that cannot physically fit a trip is
  reported with an explicit reason, never silently skipped or faked.

## 2. What gets masked (and what does not)

Masked inside every outage window (`configs/evaluation_config.yaml` →
`blackout.mask_columns`, mirrors `src/preprocessing/synchronization.GNSS_COLS`):

| Column | Meaning |
|---|---|
| `latitude_deg`, `longitude_deg`, `altitude_m` | position fix |
| `speed_kmh` | GNSS speed |
| `position_accuracy_m` | GNSS accuracy |
| `gps_heading_deg` | GNSS heading |
| `gps_satellites` | fix quality indicator |

**Never touched:** `timestamp`/`datetime`/`time_since_start_ms`, all IMU columns
(`accel|gyro|mag|gravity|orientation_*`), all Phase 2 derivatives
(`gravity_est_*`, `linear_accel_*`, `*_cal`, `orient_*`, `*_aligned`),
`trip_id`, `source_file`, `sync_status`, `category`, `driver`, and everything
`reference_*`.

Rows are **never deleted**; values outside the outage are **byte-identical** to
the source (enforced by the validation report).

## 3. Added columns

| Column | Type | Meaning |
|---|---|---|
| `gnss_available` | bool | explicitly `False` exactly on masked rows. The Phase 1 schema has **no** native availability field (GNSS is forward-filled), so this is the team-wide convention. |
| `blackout_phase` | str | `pre_blackout` / `blackout` / `inter_blackout` / `post_blackout` relative to the outage(s) |
| `blackout_id` | float | 0,1,… for rows inside each outage, `NaN` otherwise |
| `reference_latitude_deg`, `reference_longitude_deg`, `reference_speed_kmh`, `reference_heading_deg`, `reference_height_m` | float | offline vehicle trajectory resampled onto the smartphone grid (or all `NaN`) |
| `reference_available` | bool | `True` only when a synchronized vehicle reference exists for the trip and the sample is inside its time coverage |
| `reference_source` | str | `"vehicle"` when attached, else `"none"` |

## 4. Runtime vs offline reference (READ BEFORE USING)

The blackout dataset deliberately **mixes runtime inputs and ground truth** in
one file with a strict prefix rule:

- **Runtime inputs** = everything **except** columns starting with `reference_`.
  This is what a model / navigation engine may consume at inference time
  (including the already-masked GNSS fields and the availability/phase columns).
- **Offline reference** = the `reference_*` columns. Use them ONLY to compute
  evaluation metrics (position error, drift, endpoint error, trajectory
  deviation). **Never** feed a `reference_*` column into the runtime model.

Programmatic separation (always use these, never manual column lists):

```python
from src.data.dataset_manager import DatasetManager
dm  = DatasetManager("data/raw", "data/processed")
df  = dm.load_blackout_scenario("m__blk30s_00")   # full frame
run = dm.runtime_frame(df)                         # runtime inputs (no reference_*)
ref = dm.reference_frame(df)                       # offline reference only
```

If the trip has no synchronized vehicle reference (e.g. `m`, `s1`, `s2`), the
`reference_*` columns are all `NaN` and `reference_available` is `False` —
ground truth for those trips falls back to the smartphone GNSS *outside* the
outage. No reference is ever fabricated.

## 5. Semantics & guarantees

- **Duration is real.** An outage is the window `[start_time, start_time +
  duration]` over the trip's actual timestamps; every row inside is masked. The
  spanned duration stored in the metadata (`masked_end_time - masked_start_time`)
  comes from the data, never assumed from the nominal sample rate.
- **Phases.** `pre_blackout` = rows before the first outage; `blackout` = inside
  any outage; `inter_blackout` = between outages (GNSS available again);
  `post_blackout` = after the last outage. (The switching/gap logic itself is
  Shatakshi's scope — this data just labels the phases.)
- **Fit check.** A scenario requires
  `duration·n + min_gap·(n-1) + min_pre + min_post ≤ trip_span`
  (gaps only when overlaps are disallowed). Otherwise the generator raises
  `BlackoutImpossibleError` with reason `trip_too_short` / `invalid_duration` /
  `insufficient_pre_post_gap`-style detail. The CLI prints and skips those.
- **Multiple intervals.** Configurable (default 1). Interval starts are drawn
  deterministically; disjoint with `min_gap_between_blackouts_s` between them
  unless `allow_overlap: true`.

## 6. Generation

```bash
python scripts/create_blackouts.py                          # all calibrated trips, all durations
python scripts/create_blackouts.py --trip m --duration 5 --duration 30
python scripts/create_blackouts.py --trip vw16b --duration 10   # attaches vehicle reference
python scripts/create_blackouts.py --seed 42 --n-scenarios 3    # more scenarios per duration
python scripts/create_blackouts.py --n-intervals 2 --duration 20 # two outages per scenario
```

CLI flags: `--trip` (repeatable/comma) · `--duration` (repeatable) ·
`--n-intervals` · `--seed` (deterministic generation seed) · `--random-seed` ·
`--n-scenarios` · `--limit` · `--source {calibrated,processed}` · `--config`.

Everything is configured in `configs/evaluation_config.yaml` — durations, seed,
number of scenarios per duration, feasibility constraints (min trip duration,
min pre/post GNSS), mask columns, reference columns and output layout. Nothing
scenario-critical is hard-coded in Python.

## 7. Output layout

```
data/blackout/
├── 5s/    m__blk5s_00.parquet + m__blk5s_00_metadata.json   …
├── 10s/   m__blk10s_00.parquet + …                          (also vw16b__blk10s_00)
├── 20s/ 30s/ 60s/ 120s/                                     …
└── scenarios_index.json        # global index of every scenario produced
```

Each `*_metadata.json` records the scenario spec, the realized mask (interval
start/end, samples masked, phases) and `has_reference`, so results are fully
reproducible from the seed. The directory is **gitignored** — regenerate it at
any time (the Phase 3 reference set uses seed 2024, 1 scenario/duration).

## 8. Validation & quality gates

`src/data/blackout_validation.py` provides two functions used before writing
anything to disk:

- `validate_trip_frame(df)` — the calibrated input is sane (timestamps, sensor
  availability, calibration columns, GNSS availability, single trip id, split
  membership when provided).
- `validate_blackout_frame(source, blackout, ...)` — hard invariants of the
  output: GNSS is `NaN` exactly where `gnss_available` is False, inside outages;
  every other column is byte-identical to the source; no rows added/deleted;
  availability agrees with `blackout_phase`; intervals are disjoint (unless
  `allow_overlap`); timestamps stay monotonic and duplicate-free.

Every check yields a report entry (`ok`/`warn`/`fail`); a failed scenario is
**not written**. Nothing is silently "fixed".

```python
from src.data.blackout_validation import validate_blackout_frame
report = validate_blackout_frame(source, blackout, mask_columns=..., allow_overlap=False)
print(report.summary())
report.assert_ok("blackout invariants")   # raises with the full report on failure
```

## 9. Tests (47 new Phase 3 tests)

`tests/simulation/` covers: masking of the 7 GNSS fields; IMU/timestamp/trip-id
preservation; row counts; `gnss_available`/phase consistency; real-time
durations (5/10/30/60/120 s closed-form row expectations); multiple disjoint
intervals with min gap; explicit errors for too-long outages and insufficient
pre/post gaps; seeded determinism (same seed ⇒ identical frames, different seeds
⇒ different placement); empty-window intervals; scenario id/file safety and
counts; reference attach/none/fabrication-avoidance; runtime/reference split;
the `DatasetManager` blackout API; and every validation failure mode.

## 10. Handoff to Tanishk & Shatakshi

- **Data source for evaluation:** `dm.load_blackout_scenario(...)` or the
  Parquet directly. Channel/columns follow the Phase 2 calibrated schema plus
  the three annotation columns and the `reference_*` offline set.
- **Tanishk (ML):** train/validate speed/position/heading models on the runtime
  frame (`dm.runtime_frame`) — note `gnss_available` is your per-sample mask
  indicator, and the masked GNSS is `NaN`, not stale.
- **Shatakshi (navigation/fusion):** use `blackout_phase` to segment
  pre-blackout / blackout / recovery behavior; compute your seamless-switching
  evaluation against `dm.reference_frame` only. Duration truth lives in
  `*_metadata.json` (`realization.intervals[].masked_start/end_time`).
- Re-generate with a different `--seed` for fresh interval placement, or add
  `--n-scenarios N` for more trials per duration/trip.

## 11. Scope & limitations

- Ground truth exists **only** where a synchronized vehicle reference was
  produced (currently `vw16b`, `vta10`); other trips report `reference_available
  = False`. Extending reference coverage is part of Phase 1 synchronization, not
  Phase 3.
- GNSS is forward-filled by Phase 1, so a "masked" cell carries `NaN` (there is
  nothing else to remove). The `gnss_available` column is the explicit,
  authoritative indicator.
- The simulator cuts availability; it does not (and must not) simulate degraded
  GNSS, multipath or drift inside the outage - that is model work upstream.