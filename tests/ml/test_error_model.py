"""tests/ml/test_error_model.py - D-T5 coverage."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.models.fusion_correction.inference import (
    DEFAULT_ARTIFACT,
    DEFAULT_CONFIDENCE_REFERENCE_M,
    RandomForestErrorModel,
)
from src.navigation.engine.model_interface import ErrorModel

from .conftest import needs_artifact, synthetic_window


def test_adapter_implements_protocol():
    assert issubclass(RandomForestErrorModel, ErrorModel)


def test_fallback_when_artifact_missing(tmp_path):
    model = RandomForestErrorModel(tmp_path / "missing.joblib")
    assert not model.available
    err, conf = model.predict_error(synthetic_window())
    assert err is None and conf is None


@needs_artifact(DEFAULT_ARTIFACT)
def test_artifact_predicts_finite_error_and_confidence():
    model = RandomForestErrorModel()
    assert model.available
    model.set_speed_provider(lambda: 5.0)
    model.set_gnss_age_provider(lambda: 30.0)
    err, conf = model.predict_error(synthetic_window(seed=5))
    assert err is not None and conf is not None
    assert np.isfinite(err) and err >= 0.0
    assert 0.0 < conf <= 1.0
    assert conf == pytest.approx(math.exp(-err / DEFAULT_CONFIDENCE_REFERENCE_M))


@needs_artifact(DEFAULT_ARTIFACT)
def test_error_scales_linear_with_gnss_age():
    model = RandomForestErrorModel()
    win = synthetic_window(seed=6)
    model.set_speed_provider(lambda: 3.0)
    model.set_gnss_age_provider(lambda: 30.0)
    e30, _ = model.predict_error(win)
    model.set_gnss_age_provider(lambda: 60.0)
    e60, _ = model.predict_error(win)
    assert e60 == pytest.approx(2.0 * e30, rel=1e-9)


@needs_artifact(DEFAULT_ARTIFACT)
def test_non_finite_age_degrades_to_zero():
    for bad in [float("inf"), float("nan"), float("-inf")]:
        model = RandomForestErrorModel()
        model.set_speed_provider(lambda: 5.0)
        model.set_gnss_age_provider(lambda: bad)
        err, conf = model.predict_error(synthetic_window(seed=7))
        assert err is not None and conf is not None
        assert np.isfinite(err) and err >= 0.0
        assert np.isfinite(conf)

    model = RandomForestErrorModel()
    model.set_speed_provider(lambda: float("inf"))
    model.set_gnss_age_provider(lambda: 60.0)
    err, conf = model.predict_error(synthetic_window(seed=7))
    assert err is not None and np.isfinite(err) and err >= 0.0


@needs_artifact(DEFAULT_ARTIFACT)
def test_negative_age_clamped_to_zero():
    model = RandomForestErrorModel()
    model.set_speed_provider(lambda: 5.0)
    model.set_gnss_age_provider(lambda: -5.0)
    err, _ = model.predict_error(synthetic_window(seed=8))
    assert err == pytest.approx(0.0)