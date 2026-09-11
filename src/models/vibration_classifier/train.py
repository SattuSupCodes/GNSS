"""D-T3 training: Random Forest vibration classifier.

Trains a lightweight, CPU-fast scikit-learn classifier on the derived
stationary / normal / vibration labels, evaluates on held-out validation and
test trips (trip-level split, no intra-trip leakage), and saves:
    models/vibration_classifier.joblib
    models/vibration_classifier_metrics.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.models.vibration_classifier.dataset import (
    CLASSES,
    build_dataset,
    class_counts,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = REPO_ROOT / "models" / "vibration_classifier.joblib"
METRICS_PATH = REPO_ROOT / "models" / "vibration_classifier_metrics.json"

SEED = 42
N_ESTIMATORS = 300
MAX_DEPTH = 20


def _label_to_int(y: np.ndarray) -> np.ndarray:
    return np.asarray([CLASSES.index(v) for v in y], dtype=int)


def train():
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import (
        accuracy_score,
        classification_report,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )

    print("Building D-T3 datasets (this reads calibrated trips)...")
    X_train, y_train, names, trips_train = build_dataset("train")
    X_val, y_val, _, trips_val = build_dataset("validation")
    X_test, y_test, _, trips_test = build_dataset("test")
    print(f"  train {X_train.shape}  val {X_val.shape}  test {X_test.shape}")
    print("  class balance (train):", class_counts(y_train))

    clf = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        max_depth=MAX_DEPTH,
        random_state=SEED,
        n_jobs=-1,
    )
    clf.fit(X_train, _label_to_int(y_train))

    def evaluate(X, y, trips, split):
        y_pred_int = clf.predict(X)
        y_pred = np.asarray([CLASSES[int(v)] for v in y_pred_int])
        y_int = _label_to_int(y)
        return {
            "split": split,
            "accuracy": float(accuracy_score(y_int, y_pred_int)),
            "precision_weighted": float(precision_score(y_int, y_pred_int, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_int, y_pred_int, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_int, y_pred_int, average="weighted", zero_division=0)),
            "class_report": classification_report(y_int, y_pred_int, target_names=CLASSES, output_dict=True, zero_division=0),
            "confusion_matrix": confusion_matrix(y_int, y_pred_int).tolist(),
            "class_counts": class_counts(y),
            "n_trips": len(set(trips)),
        }

    val_metrics = evaluate(X_val, y_val, trips_val, "validation")
    test_metrics = evaluate(X_test, y_test, trips_test, "test")

    metrics = {
        "model": "RandomForestClassifier",
        "classes": CLASSES,
        "feature_names": names,
        "n_train_samples": int(len(X_train)),
        "n_train_trips": len(set(trips_train)),
        "seed": SEED,
        "label_rule": {
            "stationary_speed_kmh_threshold": 0.5,
            "vibration_mag_abs_dev_mps2": 0.35,
            "vibration_jerk_std_mps2": 0.8,
            "vibration_gyro_jerk_radps": 0.25,
        },
        "validation": val_metrics,
        "test": test_metrics,
    }

    import joblib

    joblib.dump(clf, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\nSaved {MODEL_PATH}")
    print(f"Saved {METRICS_PATH}")
    print(f"\nD-T3 validation accuracy: {val_metrics['accuracy']:.4f}")
    print(f"D-T3 test      accuracy: {test_metrics['accuracy']:.4f}")
    return metrics


if __name__ == "__main__":
    train()