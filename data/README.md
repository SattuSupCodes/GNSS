# Data Directory

## Dataset

**Primary dataset:** IO-VNBD (ISRO Vehicle Navigation Benchmark Dataset)

This directory contains the complete data pipeline from raw downloads to model-ready splits.

## Smartphone-Only Principle

- **Smartphone sensor data** (accelerometer, gyroscope, magnetometer, GNSS) is the **primary input** for all runtime inference
- **Vehicle-side data** (vehicle IMU, wheel speed, vehicle GPS, CAN/OBD) is **NOT a runtime dependency**
- Vehicle-side / reference data may **only be used offline** for:
  - Ground truth trajectory generation
  - Supervised learning labels (speed, heading, position)
  - Evaluation benchmarks
  - GNSS blackout scenario validation

## Directory Structure

```
data/
├── raw/              # Original IO-VNBD downloads (immutable, gitignored)
├── processed/        # Preprocessed trip Parquets + fitted metadata
│   └── trip_<id>.parquet
├── processed/synchronized/   # Time-aligned S + V reference streams per trip
├── calibrated/       # Phase 2: gravity/cal/orient/aligned enriched trips
├── splits/           # Trip-level train/validation/testing split lists
├── training/         # Phase 2: fixed-length window sequences (per split)
├── validation/       # Phase 2: fixed-length window sequences (per split)
├── testing/          # Phase 2: fixed-length window sequences (per split)
├── blackout/         # Phase 3: GNSS-denied blackout scenarios for evaluation
└── maps/             # Road network data (OSM/Mapbox) for map matching (future)
```

(`interim/` is not used; window sequences in `training|validation|testing/`
are long-format frames grouped by `sequence_id`.)

## Data Flow

```
IO-VNBD Raw (data/raw/)
    ↓  scripts/download_dataset.py  (Git LFS clone/verify)
Smartphone extraction (src/data/: schema, loader, extractor)
    ↓  scripts/prepare_dataset.py    (per trip)
Cleaning, outlier removal, low-pass, uniform resample, z-score, ENU coords
    ↓  (src/preprocessing/, configs/preprocessing_config.yaml)
Trip Parquerts (data/processed/trip_<id>.parquet)
    ↓  scripts/calibrate_dataset.py  (Phase 2)
Calibrated trips (gravity_est/cal/orient/aligned) → data/calibrated/
    ↓  scripts/generate_sequences.py (Phase 2, split-aware)
Fixed-length window sequences → data/{training,validation,testing}/
    ↓  scripts/create_blackouts.py (Phase 3)
GNSS-denied scenarios (GNSS masked, reference kept) → data/blackout/
    ↓
Smartphone-only runtime input; vehicle used offline as ground truth
```

> Smartphone-only principle: the runtime model consumes **only** smartphone
> sensors. Vehicle data is `is_reference=True` and used offline (labels,
> evaluation, GNSS-blackout validation).

## Processing a Trip

```bash
python scripts/prepare_dataset.py --trip vw16b        # construct one trip
python scripts/prepare_dataset.py --all               # construct all 72
python scripts/synchronize_data.py --trip vw16b        # S + aligned V reference
python scripts/calibrate_dataset.py                    # Phase 2 calibration
python scripts/generate_sequences.py                   # Phase 2 window sequences
python scripts/create_blackouts.py                     # Phase 3 GNSS blackouts
```

See `docs/preprocessing.md` for the full pipeline chain and sync semantics,
`docs/calibration.md` for the Phase 2 calibration + sequence layer, and
`docs/evaluation.md` for the Phase 3 GNSS-blackout simulation.

## Getting the Dataset (Step by Step)

> **TL;DR** The data lives in a **public** GitHub repo that uses **Git LFS**.
> You must clone it with Git LFS enabled, otherwise you'll only get tiny LFS
> pointer files (~130 bytes) instead of the real CSV data.

### Option A — Using the download script (recommended)

The repository ships a helper script that does everything for you:

```bash
# 1. (Only once, if you don't have it) install Git LFS:
#    Windows: https://git-lfs.com/  →  run `git lfs install`
#    macOS:   brew install git-lfs && git lfs install
#    Linux:   sudo apt install git-lfs && git lfs install

# 2. Run the downloader (clones + verifies into data/raw by default)
python scripts/download_dataset.py

# want it elsewhere?
python scripts/download_dataset.py --target D:/somewhere/IO-VNBD
```

### Option B — Manual clone (identical result)

1. Clone the project repo (this repo):

   ```bash
   git clone https://github.com/afx786/GNSS.git
   cd GNSS
   ```

2. Make sure Git LFS is enabled for the clone:

   ```bash
   git lfs install
   ```

3. Clone the **dataset** repo (public, ~1.4 GB of CSVs):

   ```bash
   git clone https://github.com/onyekpeu/IO-VNBD.git data/raw
   cd data/raw && git lfs pull && cd ../..
   ```
   or, if `data/raw` already exists locally, clone into a temp folder and move
   the contents over.

4. Verify you got real data (a resolved file is tens–hundreds of KB, not ~130
   bytes):

   ```bash
   Get-ChildItem data/raw -Recurse -Filter *.csv | Where-Object Length -lt 1000
   ```
   The command above should return **nothing** if the download worked.

### What "cloning the dataset" means & why LFS matters

- The official dataset repository (`onyekpeu/IO-VNBD`) stores every `*.csv` in
  **Git LFS** (see its `.gitattributes`).
- If you download the folder as a ZIP from the GitHub web UI, you get **only
  the LFS pointer files**, not the data. That is why the files look like:

  ```
  version https://git-lfs.github.com/spec/v1
  oid sha256:744cdb28...
  size 221088
  ```

  and are ~130 bytes. This is **not** the real data.

- Cloning with Git LFS (`git lfs pull`) replaces those pointers with the actual
  sensor CSVs (GPS, accelerometer, gyroscope, magnetometer, timestamps).

### Cross-platform notes

| OS | Git LFS install |
|----|-----------------|
| Windows | `winget install Git.LFS` or download from https://git-lfs.com |
| macOS | `brew install git-lfs` |
| Linux (Debian/Ubuntu) | `sudo apt-get install git-lfs` |

After installing once, run `git lfs install` in the repo to enable the filter.

## Important Notes

- Never commit raw or processed data to git (see `.gitignore`)
- `data/processed/*.parquet` and `data/splits/*.txt` are build outputs — the
  pipeline regenerates them from `data/raw/`
- All preprocessing is configuration-driven via `configs/preprocessing_config.yaml`
- Dataset splits are **trip-level** (no row-level leakage): the 72 smartphone
  trips split 50/11/11 into train/validation/testing
- `sync_status` distinguishes the row-aligned (`synchronised`) and separate
  (`unsynchronised`) recordings of the same trip id — they are distinct and
  **never merged**
- Vehicle data is always reference-only (`is_reference=True`)
- `data/blackout/` contains only generated artifacts (gitignored): `5s|10s|20s|
  30s|60s|120s/` subdirs with one Parquet + one metadata JSON per scenario, plus
  `scenarios_index.json`. Regenerate any time with `scripts/create_blackouts.py`
- The full dataset is **not** committed to this repo (it is gitignored); each
  teammate downloads it locally using the steps above.