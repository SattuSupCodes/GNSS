# IO-VNBD Dataset — Actual Discovered Structure

This document records what was actually found in the local copy of the IO-VNBD
dataset (`data/raw`) on 2026-09-05, after cloning the official GitHub repository
(`https://github.com/onyekpeu/IO-VNBD`) with Git LFS enabled.

---

## 1. Availability Status

- **Real CSV data is present.** All 382 CSV files are actual data, **none** are
  Git LFS pointer files. Every file is > 1 KB.
- Total raw size on disk: ~1.44 GB (382 CSVs + 72 JPG + 2 README + 1 zip).
- The large `Synchronised V abd S datasets.zip` (203 MB) is a redundant archive
  of the synchronised CSVs; it is **not** used by the pipeline.

---

## 2. Top-Level Layout

```
data/raw/
├── README.md                          # dataset description
├── README_1.pdf                       # dataset paper
├── Synchronised V abd S datasets.zip  # 203 MB archive (unused by pipeline)
├── Synchronised V abd S datasets/     # "SYNC" — row-aligned S/V pairs
└── Unsynchronised V and S Dataset/    # "UNSYNC" — separate S and V recordings
```

---

## 3. Synchronised Dataset

Path: `data/raw/Synchronised V abd S datasets/`

| Subfolder | S files | V files | JPG |
|-----------|---------|---------|-----|
| `Categorised IOVNB Dataset/` | 72 | 72 | 72 |
| `Uncategorised IOVNB Dataset/S-Dataset/` | 72 | — | — |
| `Uncategorised IOVNB Dataset/V-Dataset/` | — | 72 | — |

- **72 smartphone trips**, each with a paired vehicle recording (same base trip id).
- The categorised layout groups files by trip folder:
  `Categorised IOVNB Dataset/<Driver>/<trip>/S-<trip>.csv`, `V-<trip>.csv`, `V-<trip>.JPG`.
- The uncategorised layout flattens them into `S-Dataset/` and `V-Dataset/`.
- **Smartphone and vehicle rows are row-synchronised** (same row count, same
  10 Hz frame). Verified on `S-Vw16b.csv` / `V-Vw16b.csv` (both 1126 rows).

### Trip IDs (sync, smartphone)

```
m s1 s2 s3 s3a s3b s4 vfa01 vfa02 vta10..vta17 (excl vta18) vta1a vta1b vta2..vta9
vta19..vta30 vtb1..vtb12 vw1..vw17 (excl vw14c? incl vw14a/14b) y1
```

72 unique smartphone trip ids (`<trip>.lower()` set).

### Category/Driver metadata

Trip naming encodes scenario groups (from the dataset README):

| Prefix | Meaning |
|--------|---------|
| `ta` / `tb` | A-road / B-road driving with combined scenarios |
| `w` | Chip-tar / country / wet-road, hard-braking variants |
| `fa` / `fb` | Motorway / city driving, traffic |
| `S1..S4` | Driver A urban perimeter trips |
| `M` | Driver B |
| `Y1` | Driver D |
| `St` | Driver C (unsync only) |
| `Vf` / `Vta` / `Vtb` / `Vw` | Driver E category folders |

Driver attribution is available from the folder names
(`S (Driver A)`, `M (Driver B)`, `Y (Driver D)`, `V* (Driver E)`).

---

## 4. Unsynchronised Dataset

Path: `data/raw/Unsynchronised V and S Dataset/`

| Subfolder | S files | V files |
|-----------|---------|---------|
| `Categorised IOVNB (V) Dataset/...` | — | 11 |
| `Uncategorised IOVNB (V and S) Dataset/S-Dataset/` | 72 | — |
| `Uncategorised IOVNB (V and S) Dataset/V-Dataset/` | — | 11 |

- **72 smartphone trips**, same trip-id set as the synchronised dataset, but the
  recordings are **not** row-aligned with the synchronised versions (file sizes
  differ from the sync S files by ~5 bytes to ~MBs).
- Only 11 trips have a paired vehicle file here; 63 smartphone trips have no
  vehicle pair in this folder.
- The categorised V files here are extra vehicle recordings not present in the
  synchronised categorised set (e.g. `St1`, `St4`, `Vf*` with `b/c/d/e/f/g`
  suffixes).

**Pipeline decision:** the smartphone S files are the runtime source. The
unsynchronised S files are distinct recordings and are preserved with
`sync_status = "unsynchronised"`; they will not be merged with the sync files.

---

## 5. Smartphone CSV Columns (S- files)

24 columns (cp1252 encoded, units embedded in headers). Header has inconsistent
leading whitespace and one trailing-space quirk; the loader normalizes names.

| # | Raw header | Canonical name | Units | Role |
|---|------------|----------------|-------|------|
| 0 | `GPS LATITUDE (degrees)` | `latitude_deg` | deg | GNSS |
| 1 | ` GPS LONGITUDE (degrees)` | `longitude_deg` | deg | GNSS |
| 2 | ` GPS ALTITUDE (m)` | `altitude_m` | m | GNSS |
| 3 | ` GPS SPEED (Kmh)` | `speed_kmh` | km/h | GNSS |
| 4 | ` GPS ACCURACY (m)` | `position_accuracy_m` | m | GNSS |
| 5 | ` GPS ORIENTATION (°)` | `gps_heading_deg` | deg | GNSS |
| 6 | `GPS SATELLITES IN RANGE` | `gps_satellites` | count | GNSS |
| 7 | ` TIME SINCE START (ms)` | `time_since_start_ms` | ms | time |
| 8 | ` DATE (YYYY-MO-DD HH-MI-SS_SSS)` | (raw date string) | — | time |
| 9-11 | ` ACCELEROMETER X|Y|Z (m/s²)` | `accel_x|y|z` | m/s² | IMU |
| 12-14 | ` GRAVITY X|Y|Z (m/s²)` | `gravity_x|y|z` | m/s² | IMU |
| 15-17 | ` GYROSCOPE X|Y|Z (rad/s)` | `gyro_x|y|z` | rad/s | IMU |
| 18-20 | ` MAGNETIC FIELD X|Y|Z (μT)` | `mag_x|y|z` | μT | mag |
| 21 | ` ORIENTATION (Azimuth) (°)` | `orientation_azimuth_deg` | deg | orientation |
| 22 | ` ORIENTATION (Pitch) (°)` | `orientation_pitch_deg` | deg | orientation |
| 23 | ` ORIENTATION (Roll ) (°)` | `orientation_roll_deg` | deg | orientation |

### Observed sampling (verified)

- Smartphone IMU/GNSS rows: **10 Hz** (median Δt = 0.100 s; min 0.098, max 0.103 s).
- GNSS fields are updated ~1–10 % of rows (≈ once per second or less
  frequently); for stationary segments the lat/lon repeats exactly. Data is
  *row-synchronised at 10 Hz*, not interpolated.
- Timestamps: no duplicates, strictly monotonic within each file.
- Missing values: none observed in the sampled files; infinite values: none.

---

## 6. Vehicle CSV Columns (V- files)

These are **reference-only** and are NEVER used as runtime inputs.

29 columns: satellite count, time-since-start-of-day (seconds), lat/lon,
velocity (km/h), heading, height, vertical velocity, sample period, steering
angle, wheel speeds (×4), yaw rate, indicated speed, longitudinal/lateral
acceleration (g), handbrake, gear requested/gear, engine speed, coolant temp,
clutch, brake pressure, brake position, battery voltage, air temp, accelerator
pedal position.

---

## 7. Missing / Unavailable Data

- No GNSS **course-over-ground** column separate from `GPS ORIENTATION` (the
  orientation column is treated as GNSS heading when present).
- No smartphone barometer/pressure column.
- No explicit sensor-rate metadata columns (rates must be inferred from
  timestamps; observed 10 Hz for both phone and vehicle rows).
- Vehicle pair for the unsynchronised S recordings is largely absent (63 of 72
  trips V-only missing).
- No separate labels/annotations files; scenario categories are encoded in file
  names and folder names.

## 8. What the Pipeline Uses

- Runtime inputs: smartphone `S-*.csv` — accelerometer, gyroscope, magnetometer,
  GNSS (lat/lon/speed/accuracy/heading), timestamps.
- Reference (offline, evaluation only): paired `V-*.csv` when a trip has one.
- The loader deliberately excludes vehicle columns from the smartphone output.