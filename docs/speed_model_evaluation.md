# Speed Model Evaluation Report

SPEED-ML workstream (D-T2 + D-T1 baselines). All metrics below are computed
on the **held-out test split** (`data/testing/sequences.parquet`, n = 183,200
masked per-sample targets, sequence length 100, input size 9) using the same
masked RMSE/MAE definition for every model. Values are produced by
`scripts/evaluate.py`, which re-loads each artifact and re-runs inference —
nothing is copied from training logs.

## Comparison

| Model | RMSE (km/h) | MAE (km/h) | Artifact |
|---|---:|---:|---|
| LSTM | 7.953 | 5.960 | `models/speed_lstm.pt` |
| GRU | 6.446 | 5.039 | `models/speed_gru.pt` |
| TCN | 6.004 | 4.617 | `models/speed_tcn.pt` |
| Linear Regression (D-T1) | 5.851 | 4.449 | `models/speed_baseline_linear.joblib` |
| Random Forest (D-T1) | 5.655 | 4.231 | `models/speed_baseline_random_forest.joblib` |
| XGBoost (D-T1) | 5.665 | 4.232 | `models/speed_baseline_xgboost.joblib` |

(Raw `models/speed_model_comparison.csv` updates automatically every time
`scripts/evaluate.py` runs.)

### Notes / caveats

- Every model is trained on the same training split, seeded with `seed=42`,
  and evaluated on the same test split with the same masked target definition.
- **Test split has changed since the LSTM was originally evaluated.** The
  committed `speed_lstm_metrics.json` reports RMSE 7.877 on an earlier, larger
  test split (n = 425,600). The sequence files on disk were regenerated
  (smaller splits), so fresh re-evaluation of the SAME LSTM artifact on the
  current test split yields 7.953 / 5.960 (n = 183,200). Training-time test
  metrics for GRU and TCN are reproduced exactly by `scripts/evaluate.py`,
  confirming the evaluation protocol is consistent across all models.
- **Validation split lacks calibrated (`*_cal`) columns.** The dataset now
  falls back to the base sensor channels for such files (logged warning) so
  training runs on all three splits. Training/test still use calibrated
  channels.
- Baselines use strictly-causal per-timestep features (instant value +
  expanding mean + expanding std), so no future information leaks.
  Random-forest/XGBoost training rows are capped (seeded subsample of 250k)
  purely for CPU time; the test evaluation always uses every sample.

## Runtime integration

The navigation engine now consumes the trained speed model through the
existing D-S7 contract:

```
navigation engine (IDREngine)
        <-update_ml(MLNavigationOutput)-
CompositeMLInference.evaluate(timestamp, window)
        |
TrainedSpeedModel.predict_speed(window)   (km/h -> m/s, window mean + std)
        |
SpeedEstimator.predict((100, 9))          (feature-scales internally)
        |
trained LSTM checkpoint (models/speed_lstm.pt)
```

Wiring details:

- `configs/navigation_config.yaml` -> `ml.enabled: true`, `ml.model: "lstm"`
  (selecting `gru`/`tcn` reuses the same code path and artifacts).
- `src/navigation/engine/model_interface.py` gains `TrainedSpeedModel` (a
  `SpeedModel` adapter) and `build_ml_inference()`; artifacts are resolved
  relative to the repository root.
- `src/engine/engine_trip_runner.py` builds the ML inference when enabled and,
  inside `run_trip`, buffers a 100-sample calibrated sensor window and feeds
  `engine.ml_inference.evaluate(...) -> engine.update_ml(...)` every sample.
- **Fallback is preserved.** If the artifact is missing, the configured model
  is unknown, inference raises, or `ml.enabled` is false, the engine falls
  back to `FallbackMLInference` (classical behaviour) and never crashes.

## Tests

`python -m pytest -q` -> **278 passed**. New focused tests live in
`tests/models/test_speed_models.py` (model construction, TCN causality,
artifact loading, masked metrics, baseline fit/predict/persistence,
`CompositeMLInference` speed integration, `TrainedSpeedModel` degradation on
bad/nonexistent artifacts, dataset column fallback).