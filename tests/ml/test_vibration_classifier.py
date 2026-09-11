"""tests/ml/test_vibration_classifier.py - D-T3 coverage."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.vibration_classifier.dataset import CLASSES, label_window
from src.models.vibration_classifier.inference import (
    DEFAULT_ARTIFACT,
    FALLBACK_CLASS,
    RandomForestVibrationClassifier,
)
from src.navigation.engine.model_interface import VibrationClassifier

from .conftest import needs_artifact, synthetic_window


def test_label_window_is_deterministic_physical():
    # Below the stationary speed threshold -> stationary regardless of IMU.
    assert label_window(0.1, {"accel_mag_mean_abs_dev": 1.0}) == "stationary"
    # Moving + high vertical energy -> vibration.
    assert (
        label_window(
            5.0,
            {
                "accel_mag_mean_abs_dev": 0.9,
                "jerk_z_std": 0.1,
                "gyroz_jerk_std": 0.1,
            },
        )
        == "vibration"
    )
    # Moving + high jerk -> vibration.
    assert (
        label_window(
            5.0,
            {
                "accel_mag_mean_abs_dev": 0.1,
                "jerk_z_std": 1.2,
                "gyroz_jerk_std": 0.1,
            },
        )
        == "vibration"
    )
    # Moving + high yaw jerk -> vibration.
    assert (
        label_window(
            5.0,
            {
                "accel_mag_mean_abs_dev": 0.1,
                "jerk_z_std": 0.1,
                "gyroz_jerk_std": 0.4,
            },
        )
        == "vibration"
    )
    # Moving + smooth -> normal.
    assert (
        label_window(
            5.0,
            {
                "accel_mag_mean_abs_dev": 0.1,
                "jerk_z_std": 0.1,
                "gyroz_jerk_std": 0.1,
            },
        )
        == "normal"
    )


def test_adapter_implements_protocol():
    assert issubclass(RandomForestVibrationClassifier, VibrationClassifier)


def test_fallback_when_artifact_missing(tmp_path):
    clf = RandomForestVibrationClassifier(tmp_path / "missing.joblib")
    assert not clf.available
    assert clf.classify(synthetic_window()) == FALLBACK_CLASS
    probs = clf.classify_probabilities(synthetic_window())
    assert probs[FALLBACK_CLASS] == 1.0


def test_malformed_window_returns_fallback(tmp_path):
    clf = RandomForestVibrationClassifier(tmp_path / "missing.joblib")
    # Wrong-row count or NaN must not raise and must not be classified.
    assert clf.classify(np.zeros((5, 50, 6))) == FALLBACK_CLASS
    bad = synthetic_window().copy()
    bad[0, 10, 0] = np.nan
    assert clf.classify(bad) == FALLBACK_CLASS


@needs_artifact(DEFAULT_ARTIFACT)
def test_artifact_loads_and_predicts():
    clf = RandomForestVibrationClassifier()
    assert clf.available

    label = clf.classify(synthetic_window(seed=1))
    assert label in CLASSES

    probs = clf.classify_probabilities(synthetic_window(seed=1))
    assert set(probs.keys()) == set(CLASSES)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-6)


@needs_artifact(DEFAULT_ARTIFACT)
def test_consistent_across_reshape():
    clf = RandomForestVibrationClassifier()
    win = synthetic_window(seed=2)
    assert clf.classify(win[0]) == clf.classify(win)