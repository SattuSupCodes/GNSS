# Evaluation

## Overview

This directory contains the evaluation framework for comparing Intelligent Dead Reckoning approaches.

## Experimental Configurations

We systematically compare six configurations of increasing sophistication:

| # | Configuration | Description |
|---|---------------|-------------|
| 1 | **Naive INS** | Double integration of raw IMU, no correction |
| 2 | **Classical EKF/UKF** | Standard GNSS+INS fusion with hand-tuned noise |
| 3 | **AI Velocity** | Learned speed estimator replaces velocity integration |
| 4 | **AI Correction** | Learned IMU error correction (bias, scale, noise) |
| 5 | **AI + Fusion** | Learned models inside filter loop (innovation correction) |
| 6 | **AI + Fusion + Map Matching** | Full pipeline with HMM + non-holonomic constraints |

## Metrics

All configurations evaluated on:

| Category | Metrics |
|----------|---------|
| **Position** | RMSE (m), CEP50 (m), CEP95 (m), Final Displacement Error (m) |
| **Drift** | Drift % per km, Drift % per minute of GNSS denial |
| **Velocity** | MAE (m/s), RMSE (m/s), Max Error (m/s) |
| **Heading** | MAE (deg), RMSE (deg), Max Error (deg) |
| **Runtime** | Inference Latency (ms), Update Frequency (Hz) |
| **Model** | Model Size (MB), Parameters (M) |

## Directory Structure

```
evaluation/
├── metrics/              # Metric computation modules
├── experiments/          # Experiment configurations & results
│   ├── baseline_ins/     # Naive INS results
│   ├── classical_fusion/ # EKF/UKF results
│   ├── ai_velocity/      # AI speed estimation results
│   ├── ai_correction/    # AI IMU correction results
│   └── ai_map_matching/  # Full pipeline results
├── results/              # Aggregated results (CSV, JSON)
└── plots/                # Generated visualization outputs
```

## Evaluation Protocol

1. **Blackout Scenarios:** Pre-defined GNSS denial windows (30s, 60s, 120s, 300s)
2. **Cross-Session Validation:** Train on subset of sessions, test on held-out sessions
3. **Statistical Significance:** Multiple runs with different seeds, report mean ± std
4. **Ablation Studies:** Component-wise contribution analysis
5. **Real-World Validation:** Select IO-VNBD sequences with natural GNSS outages

## Running Evaluation

```bash
# Run full evaluation suite
python scripts/evaluate.py --config configs/evaluation_config.yaml

# Run specific experiment
python scripts/evaluate.py --experiment ai_velocity
```