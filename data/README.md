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
├── raw/              # Original IO-VNBD downloads (immutable)
├── interim/          # Extracted smartphone streams, partial cleaning
├── processed/        # Fully preprocessed, calibrated, synchronized data
├── synchronized/     # Time-aligned multi-sensor streams per session
├── training/         # Train splits (features + labels)
├── validation/       # Validation splits
├── testing/          # Held-out test splits
├── blackout/         # Synthetic GNSS blackout scenarios for evaluation
└── maps/             # Road network data (OSM/Mapbox) for map matching
```

## Data Flow

```
IO-VNBD Raw
    ↓
Smartphone Extraction (accel, gyro, mag, GNSS, timestamps)
    ↓
Cleaning & Outlier Removal
    ↓
Resampling (common time base, e.g., 100 Hz)
    ↓
Coordinate Transform (phone → vehicle frame)
    ↓
Calibration (bias, scale, misalignment, gravity)
    ↓
Synchronization (sensor fusion ready streams)
    ↓
Train / Val / Test Split (by session, no leakage)
    ↓
Blackout Scenario Injection (for evaluation only)
```

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
- Use `.gitkeep` files to preserve directory structure
- All preprocessing is configuration-driven via `configs/preprocessing_config.yaml`
- Dataset splits are session-based to prevent temporal leakage
- The full dataset is **not** committed to this repo (it is gitignored); each
  teammate downloads it locally using the steps above.