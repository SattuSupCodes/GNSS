"""Unified evaluation of every speed-estimation model on the held-out test set.

Writes ``models/speed_model_comparison.csv`` with one row per model:

    model | rmse_kmh | mae_kmh | samples | status | note

Models are loaded from their saved artifacts and re-evaluated on the SAME
masked per-sample ``speed_kmh`` targets as the LSTM baseline (n = 425,600).
Nothing is fabricated: models that cannot be loaded are recorded as FAILED
with the reason.
"""

from pathlib import Path
import argparse
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
import pandas as pd
import torch

from src.models.speed_estimator.dataset import SpeedSequenceDataset
from src.models.speed_estimator.train import calculate_metrics as torch_metrics
from src.models.baselines.feature_utils import (
    build_causal_features,
    calculate_metrics as numpy_metrics,
)

TEST_PATH = Path("data/testing/sequences.parquet")
MODEL_DIR = Path("models")
OUTPUT_PATH = MODEL_DIR / "speed_model_comparison.csv"

SEQUENCE_LENGTH = 100

NEURAL_ARTIFACTS = [
    ("lstm", "models/speed_lstm.pt", "models/speed_lstm_scaler.npz"),
    ("gru", "models/speed_gru.pt", "models/speed_gru_scaler.npz"),
    ("tcn", "models/speed_tcn.pt", "models/speed_tcn_scaler.npz"),
]

BASELINE_ARTIFACTS = [
    ("linear", "models/speed_baseline_linear.joblib"),
    ("random_forest", "models/speed_baseline_random_forest.joblib"),
    ("xgboost", "models/speed_baseline_xgboost.joblib"),
]


def load_neural_inputs():
    dataset = SpeedSequenceDataset(str(TEST_PATH))

    x = torch.stack([torch.from_numpy(item[0].numpy()) for item in dataset])
    y = torch.stack([torch.from_numpy(item[1].numpy()) for item in dataset])
    mask = torch.stack([torch.from_numpy(item[2].numpy()) for item in dataset])

    return x.float(), y.float(), mask.bool()


def evaluate_neural(name, model_path, scaler_path, x, y, mask):
    from src.models.speed_estimator.inference import SpeedEstimator

    estimator = SpeedEstimator(
        model_path=model_path,
        scaler_path=scaler_path,
    )

    # The neural models were trained on standardized features; the scaler is
    # bundled with each artifact, so we must apply it here too.
    scaled = estimator.scaler.transform(x.numpy())

    x_scaled = torch.from_numpy(scaled).float().to(estimator.device)

    with torch.no_grad():
        prediction = estimator.model(x_scaled)

    metrics = torch_metrics(
        prediction.cpu(),
        y,
        mask,
    )

    return {
        "model": name,
        "rmse_kmh": metrics["rmse"],
        "mae_kmh": metrics["mae"],
        "samples": metrics["samples"],
        "status": "ok",
        "note": f"arch={estimator.model.__class__.__name__}",
    }


def evaluate_baseline(name, artifact_path, features, y, mask):
    from src.models.baselines.base import ClassicalSpeedBaseline

    baseline = ClassicalSpeedBaseline.load(artifact_path)

    prediction = baseline.predict(features)

    metrics = numpy_metrics(
        y.numpy(),
        prediction,
        mask.numpy(),
    )

    return {
        "model": name,
        "rmse_kmh": metrics["rmse"],
        "mae_kmh": metrics["mae"],
        "samples": metrics["samples"],
        "status": "ok",
        "note": str(type(baseline.model).__name__),
    }


def main():

    parser = argparse.ArgumentParser(
        description="Evaluate all trained speed models on the held-out test set."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
    )
    args = parser.parse_args()

    print("=" * 70)
    print("UNIFIED SPEED MODEL EVALUATION (HELD-OUT TEST SET)")
    print("=" * 70)

    # ------------------------------------------------------ #
    # Load test inputs once
    # ------------------------------------------------------ #

    print("\nLoading test sequences...")
    x, y, mask = load_neural_inputs()
    print(f"Sequences: {x.shape[0]:,}   Valid samples: {int(mask.sum()):,}")

    features_test_np = None

    # ------------------------------------------------------ #
    # Neural models
    # ------------------------------------------------------ #

    rows = []

    for name, model_path, scaler_path in NEURAL_ARTIFACTS:
        print(f"\nEvaluating neural model: {name} ...")

        if not Path(model_path).exists() or not Path(scaler_path).exists():
            rows.append({
                "model": name,
                "rmse_kmh": np.nan,
                "mae_kmh": np.nan,
                "samples": 0,
                "status": "FAILED",
                "note": f"artifact missing: {model_path}",
            })
            continue

        try:
            result = evaluate_neural(name, model_path, scaler_path, x, y, mask)
            print(
                f"  RMSE: {result['rmse_kmh']:.4f}  "
                f"MAE: {result['mae_kmh']:.4f}  (n={result['samples']:,})"
            )
            rows.append(result)
        except Exception as error:
            print(f"  FAILED: {error}")
            rows.append({
                "model": name,
                "rmse_kmh": np.nan,
                "mae_kmh": np.nan,
                "samples": 0,
                "status": "FAILED",
                "note": str(error),
            })

    # ------------------------------------------------------ #
    # Classical baselines
    # ------------------------------------------------------ #

    for name, artifact_path in BASELINE_ARTIFACTS:
        print(f"\nEvaluating baseline: {name} ...")

        if not Path(artifact_path).exists():
            rows.append({
                "model": name,
                "rmse_kmh": np.nan,
                "mae_kmh": np.nan,
                "samples": 0,
                "status": "FAILED",
                "note": f"artifact missing: {artifact_path}",
            })
            continue

        try:
            if features_test_np is None:
                features_test_np = build_causal_features(x.numpy())

            result = evaluate_baseline(
                name,
                artifact_path,
                features_test_np,
                y,
                mask,
            )
            print(
                f"  RMSE: {result['rmse_kmh']:.4f}  "
                f"MAE: {result['mae_kmh']:.4f}  (n={result['samples']:,})"
            )
            rows.append(result)
        except Exception as error:
            print(f"  FAILED: {error}")
            rows.append({
                "model": name,
                "rmse_kmh": np.nan,
                "mae_kmh": np.nan,
                "samples": 0,
                "status": "FAILED",
                "note": str(error),
            })

    # ------------------------------------------------------ #
    # Write comparison table
    # ------------------------------------------------------ #

    table = pd.DataFrame(
        rows,
        columns=[
            "model",
            "rmse_kmh",
            "mae_kmh",
            "samples",
            "status",
            "note",
        ],
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output, index=False)

    print()
    print("=" * 70)
    print("COMPARISON TABLE")
    print("=" * 70)
    print(
        table.round(4).to_string(index=False)
    )
    print()
    print(f"Saved -> {args.output}")


if __name__ == "__main__":
    main()