"""tests/ml/test_imu_correction.py - D-T4 coverage."""

from __future__ import annotations

import numpy as np
import pytest

from src.models.imu_correction.inference import (
    DEFAULT_ARTIFACT,
    RandomForestIMUCorrectionModel,
)
from src.navigation.engine.model_interface import IMUCorrectionModel

from .conftest import needs_artifact, synthetic_window


def test_adapter_implements_protocol():
    assert issubclass(RandomForestIMUCorrectionModel, IMUCorrectionModel)


def test_fallback_when_artifact_missing(tmp_path):
    model = RandomForestIMUCorrectionModel(tmp_path / "missing.joblib")
    assert not model.available
    corr, std = model.predict_correction(synthetic_window())
    assert corr is None and std is None


def test_no_heading_returns_none(tmp_path):
    model = RandomForestIMUCorrectionModel(tmp_path / "missing.joblib")
    model.set_heading_provider(None)
    corr, std = model.predict_correction(synthetic_window())
    assert corr is None and std is None


@needs_artifact(DEFAULT_ARTIFACT)
def test_invalid_heading_returns_none():
    for bad in [float("nan"), float("inf"), float("-inf")]:
        model = RandomForestIMUCorrectionModel()
        model.set_heading_provider(lambda: bad)
        corr, _ = model.predict_correction(synthetic_window())
        assert corr is None


@needs_artifact(DEFAULT_ARTIFACT)
def test_artifact_predicts_valid_enu_correction():
    model = RandomForestIMUCorrectionModel()
    assert model.available
    model.set_heading_provider(lambda: 0.0)  # north
    corr, std = model.predict_correction(synthetic_window(seed=3))
    assert corr is not None and std is not None
    assert std == pytest.approx(1.0)
    assert corr.shape == (2,)
    assert np.isfinite(corr).all()
    # The forward prediction is clipped to +/-5 m/s^2 -> ENU magnitude <= 5.
    assert float(np.hypot(*corr)) <= 5.0 + 1e-9
    # Heading 0 => east component ~ 0 (sin(0)).
    assert abs(corr[0]) < 1e-9


@needs_artifact(DEFAULT_ARTIFACT)
def test_heading_rotation_is_consistent():
    model_0 = RandomForestIMUCorrectionModel()
    model_0.set_heading_provider(lambda: 0.0)
    model_90 = RandomForestIMUCorrectionModel()
    model_90.set_heading_provider(lambda: np.pi / 2)
    win = synthetic_window(seed=4)
    c0, _ = model_0.predict_correction(win)
    c90, _ = model_90.predict_correction(win)
    # Rotation must preserve magnitude.
    assert np.hypot(*c0) == pytest.approx(np.hypot(*c90), abs=1e-9)