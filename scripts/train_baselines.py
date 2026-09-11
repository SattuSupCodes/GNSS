"""Train and evaluate the D-T1 classical baselines.

Produces:
    models/speed_baseline_linear.joblib        + _metrics.json
    models/speed_baseline_random_forest.joblib + _metrics.json
    models/speed_baseline_xgboost.joblib       + _metrics.json

Features are the SAME causal per-timestep features used at evaluation, and the
target is the same masked per-sample ``speed_kmh`` used by the neural models.
"""

from pathlib import Path
import argparse
import json
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from src.models.baselines.feature_utils import (
    TARGET_COLUMN,
    build_causal_features,
    calculate_metrics,
    load_sequences,
)
from src.models.baselines import (
    LinearRegressionBaseline,
    RandomForestBaseline,
    XGBoostBaseline,
    _XGBOOST_AVAILABLE,
)

SEED = 42

TRAIN_PATH = Path("data/training/sequences.parquet")
VAL_PATH = Path("data/validation/sequences.parquet")
TEST_PATH = Path("data/testing/sequences.parquet")

MODEL_DIR = Path("models")

#: Keep classical training fast and reproducible; the test evaluation is all
#: on the SAME held-out test split used by the neural models.
MAX_TRAIN_ROWS = 250_000


BASELINE_FACTORIES = {
    "linear": lambda: LinearRegressionBaseline(),
    "random_forest": lambda: RandomForestBaseline(seed=SEED),
    "xgboost": lambda: XGBoostBaseline(seed=SEED),
}


def build_dataset(path: Path):
    x, y, mask = load_sequences(path)

    features = build_causal_features(x)

    return features, y, mask


def main():

    parser = argparse.ArgumentParser(
        description="Train D-T1 classical speed baselines."
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=MAX_TRAIN_ROWS,
        help="Maximum number of training rows per model.",
    )
    parser.add_argument(
        "--baseline",
        choices=list(BASELINE_FACTORIES) + ["all"],
        default="all",
    )
    args = parser.parse_args()

    np.random.seed(SEED)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("D-T1 CLASSICAL BASELINES - TRAIN + EVALUATE")
    print("=" * 70)

    print()
    print("Loading training split...")
    train_features, train_y, train_mask = build_dataset(TRAIN_PATH)

    print("Loading validation split...")
    val_features, val_y, val_mask = build_dataset(VAL_PATH)

    print("Loading test split...")
    test_features, test_y, test_mask = build_dataset(TEST_PATH)

    print()
    print(
        f"Train rows (valid): {train_mask.sum():,} / {train_mask.size:,}"
    )
    print(
        f"Test  rows (valid): {test_mask.sum():,} / {test_mask.size:,}"
    )

    chosen = list(BASELINE_FACTORIES)
    if args.baseline != "all":
        chosen = [args.baseline]
        if args.baseline == "xgboost" and not _XGBOOST_AVAILABLE:
            print("\nXGBoost is not installed; nothing to train. Recorded as FAILED.")
            return

    # Shared subsample of training rows (seeded) to keep every fit fast.
    valid_indices = np.where(train_mask.ravel())[0]

    if len(valid_indices) > args.max_rows:
        valid_indices = np.random.choice(
            valid_indices,
            size=args.max_rows,
            replace=False,
        )
        valid_indices.sort()

    rows_train = train_features.reshape(-1, train_features.shape[-1])[valid_indices]
    y_train = train_y.reshape(-1)[valid_indices]

    for name in chosen:

        print()
        print("=" * 70)
        print(f"TRAINING {name.upper()}")
        print("=" * 70)

        artifact_path = MODEL_DIR / f"speed_baseline_{name}.joblib"
        metrics_path = MODEL_DIR / f"speed_baseline_{name}_metrics.json"

        try:
            baseline = BASELINE_FACTORIES[name]()

            baseline.fit(rows_train, y_train, np.ones_like(y_train, dtype=bool))

            baseline.save(artifact_path)

            test_pred = baseline.predict(test_features)

            test_metrics = calculate_metrics(
                test_y,
                test_pred,
                test_mask,
            )

            val_pred = baseline.predict(val_features)
            val_metrics = calculate_metrics(
                val_y,
                val_pred,
                val_mask,
            )

            print()
            print(f"Validation RMSE: {val_metrics['rmse']:.4f} km/h")
            print(
                f"Test RMSE: {test_metrics['rmse']:.4f} km/h  "
                f"MAE: {test_metrics['mae']:.4f} km/h  "
                f"(n={test_metrics['samples']:,})"
            )

            record = {
                "model": name,
                "seed": SEED,
                "training_rows": int(len(valid_indices)),
                "validation_metrics": val_metrics,
                "test_metrics": test_metrics,
            }

            with open(metrics_path, "w", encoding="utf-8") as file:
                json.dump(record, file, indent=2)

            print(f"\nArtifact saved -> {artifact_path}")
            print(f"Metrics saved  -> {metrics_path}")

        except Exception as error:  # pragma: no cover - defensive reporting
            print(f"\nERROR training {name}: {error}")

            record = {
                "model": name,
                "status": "FAILED",
                "reason": str(error),
            }

            with open(metrics_path, "w", encoding="utf-8") as file:
                json.dump(record, file, indent=2)

    print()
    print("=" * 70)
    print("BASELINE TRAINING COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()