"""tests/ml/test_trained_ml_inference.py - runtime integration adapter."""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from src.navigation.engine.model_interface import (
    TRAINED_CORRECTION_MODELS,
    TrainedMLInference,
)

from .conftest import needs_artifact, synthetic_window


class _FakeVibration:
    def __init__(self, context="normal"):
        self.context = context

    def classify(self, window):
        return self.context


class _FakeIMU:
    def __init__(self, correction=(0.5, -0.2), std=1.0):
        self.correction = correction
        self.std = std

    def set_heading_provider(self, provider):
        self.provider = provider

    def predict_correction(self, window):
        return np.asarray(self.correction), self.std


class _FakeError:
    def __init__(self, error=None):
        self.error = error

    def set_speed_provider(self, provider):
        self.speed = provider

    def set_gnss_age_provider(self, provider):
        self.age = provider

    def predict_error(self, window):
        if callable(self.error):
            return self.error()
        return self.error, None


def _inference(**overrides) -> TrainedMLInference:
    inf = TrainedMLInference()
    inf._vibration = overrides.get("vibration", _FakeVibration())
    inf._imu_correction = overrides.get("imu", _FakeIMU())
    inf._error_model = overrides.get("error", _FakeError(error=120.0))
    return inf


def test_no_artifacts_yields_no_corrections(tmp_path, monkeypatch):
    inf = TrainedMLInference(repo_root=tmp_path)
    inf._load_imu_correction = lambda p: None
    inf._load_vibration = lambda p: None
    inf._load_error_model = lambda p: None
    inf._vibration = None
    inf._imu_correction = None
    inf._error_model = None
    assert not inf.available
    out = inf.evaluate(0.0, synthetic_window())
    assert out.speed_mps is None
    assert out.accel_correction_enu is None
    assert out.position_error_m is None


def test_bind_propagates_providers():
    inf = _inference()
    imu, err = inf._imu_correction, inf._error_model
    inf.bind(
        heading_provider=lambda: 1.0,
        speed_provider=lambda: 4.0,
        gnss_age_provider=lambda: 25.0,
    )
    assert imu.provider is not None
    assert err.speed is not None and err.age is not None


def test_combines_all_corrections():
    inf = _inference()
    inf.bind(
        heading_provider=lambda: 0.0,
        speed_provider=lambda: 5.0,
        gnss_age_provider=lambda: 10.0,
    )
    out = inf.evaluate(123.5, synthetic_window(seed=1))
    assert out.timestamp == 123.5
    assert out.speed_mps is None  # context normal -> no pseudo speed
    assert out.accel_correction_enu is not None
    assert out.accel_correction_std_mps2 == pytest.approx(1.0)
    assert out.position_error_m == pytest.approx(120.0)


def test_stationary_emits_zero_speed_pseudomeasurement():
    inf = _inference(vibration=_FakeVibration(context="stationary"))
    out = inf.evaluate(0.0, synthetic_window())
    assert out.speed_mps == 0.0
    assert out.speed_std_mps == pytest.approx(TrainedMLInference.STATIONARY_SPEED_STD_MPS)


def test_vibration_inflates_accel_std():
    inf = _inference(
        vibration=_FakeVibration(context="vibration"),
        imu=_FakeIMU(correction=(0.3, 0.1), std=1.0),
    )
    out = inf.evaluate(0.0, synthetic_window())
    assert out.accel_correction_std_mps2 == pytest.approx(2.0)
    assert out.accel_correction_enu == pytest.approx((0.3, 0.1))


def test_negative_error_model_output_is_rejected():
    inf = _inference(error=_FakeError(error=(-5.0, None)))
    out = inf.evaluate(0.0, synthetic_window())
    assert out.position_error_m is None


def test_infinite_error_model_output_is_rejected():
    inf = _inference(error=_FakeError(error=(math.inf, None)))
    out = inf.evaluate(0.0, synthetic_window())
    assert out.position_error_m is None


def test_failing_adapter_is_isolated():
    def boom():
        raise RuntimeError("boom")

    inf = _inference(vibration=_FakeVibration(boom), imu=_FakeIMU())
    out = inf.evaluate(0.0, synthetic_window())
    # Other adapters still deliver their corrections.
    assert out.accel_correction_enu is not None


def test_speed_window_trimmed_to_six_channels():
    inf = _inference()
    win9 = np.concatenate([synthetic_window(seed=2), np.zeros((1, 100, 3))], axis=2)
    out = inf.evaluate(0.0, win9)
    assert out.accel_correction_enu is not None


@needs_artifact(TRAINED_CORRECTION_MODELS["error_model"])
def test_live_artifacts_produce_finite_full_output():
    inf = TrainedMLInference()
    inf.bind(
        heading_provider=lambda: 0.7,
        speed_provider=lambda: 6.0,
        gnss_age_provider=lambda: 40.0,
    )
    out = inf.evaluate(7.0, synthetic_window(seed=9))
    fields = dataclasses.asdict(out)
    for key, value in fields.items():
        if isinstance(value, tuple):
            assert all(math.isfinite(v) for v in value)
        elif value is not None:
            assert math.isfinite(float(value)), key
    assert out.position_error_m is not None and out.position_error_m > 0.0