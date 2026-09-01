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

## Important Notes

- Never commit raw or processed data to git (see `.gitignore`)
- Use `.gitkeep` files to preserve directory structure
- All preprocessing is configuration-driven via `configs/preprocessing_config.yaml`
- Dataset splits are session-based to prevent temporal leakage