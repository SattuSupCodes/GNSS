"""Focused tests for the SPEED-ML workstream models and runtime glue."""

from pathlib import Path

import numpy as np
import pytest
import torch

from src.models.baselines.linear_regression import LinearRegressionBaseline
from src.models.baselines.random_forest import RandomForestBaseline
from src.models.baselines.xgboost_model import XGBoostBaseline, _XGBOOST_AVAILABLE
from src.models.baselines.feature_utils import build_causal_features, calculate_metrics
from src.models.speed_estimator.dataset import SpeedSequenceDataset
from src.models.speed_estimator.train import calculate_metrics as torch_metrics
from src.models.speed_estimator.lstm import SpeedLSTM
from src.models.speed_estimator.gru import SpeedGRU
from src.models.speed_estimator.tcn import SpeedTCN

REPO_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = REPO_ROOT / "models"

X_SHAPE = (100, 9)
BATCH = (3, 100, 9)


# ---------------------------------------------------------------------- #
# Model construction + input/output contract
# ---------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "model_class, kwargs",
    [
        (SpeedLSTM, dict(input_size=9, hidden_size=64, num_layers=2)),
        (SpeedGRU, dict(input_size=9, hidden_size=64, num_layers=2)),
        (SpeedTCN, dict(input_size=9)),
    ],
)
def test_neural_model_output_shape(model_class, kwargs):
    model = model_class(**kwargs)
    model.eval()

    x = torch.randn(*BATCH)

    with torch.no_grad():
        out = model(x)

    assert tuple(out.shape) == BATCH[:2], out.shape


def test_tcn_is_causal_no_future_leak():
    """A TCN prediction at t must not depend on samples after t."""
    model = SpeedTCN(input_size=9)
    model.eval()

    x1 = torch.randn(1, 100, 9)
    x2 = x1.clone()
    # Corrupt the future after position 50 -> first 50 predictions must match.
    x2[0, 50:, :] = torch.randn_like(x2[0, 50:, :]) * 100

    with torch.no_grad():
        out1 = model(x1)
        out2 = model(x2)

    assert torch.allclose(out1[0, :50], out2[0, :50], atol=1e-5)


# ---------------------------------------------------------------------- #
# Artifact loading + inference
# ---------------------------------------------------------------------- #


def test_estimator_loads_lstm_artifact_and_predicts():
    from src.models.speed_estimator.inference import SpeedEstimator

    model_path = MODEL_DIR / "speed_lstm.pt"
    scaler_path = MODEL_DIR / "speed_lstm_scaler.npz"

    if not (model_path.exists() and scaler_path.exists()):
        pytest.skip("speed_lstm artifacts not present")

    estimator = SpeedEstimator(
        model_path=str(model_path),
        scaler_path=str(scaler_path),
    )

    x = np.random.RandomState(0).randn(*X_SHAPE).astype(np.float32)

    prediction = estimator.predict(x)

    assert prediction.shape == (100,)
    assert np.isfinite(prediction).all()
    assert (prediction >= 0.0).all()


@pytest.mark.parametrize(
    "stem",
    ["speed_gru", "speed_tcn"],
)
def test_estimator_loads_alt_artifact(stem):
    from src.models.speed_estimator.inference import SpeedEstimator

    model_path = MODEL_DIR / f"{stem}.pt"
    scaler_path = MODEL_DIR / f"{stem}_scaler.npz"

    if not (model_path.exists() and scaler_path.exists()):
        pytest.skip(f"{stem} artifacts not present (train first)")

    estimator = SpeedEstimator(
        model_path=str(model_path),
        scaler_path=str(scaler_path),
    )

    assert estimator.model is not None
    assert estimator.model_path.match(f"{stem}.pt")


# ---------------------------------------------------------------------- #
# Metrics
# ---------------------------------------------------------------------- #


def test_masked_metrics_match_neural_definition():
    prediction = torch.tensor([[1.0, 3.0, 5.0]])
    target = torch.tensor([[1.0, 3.0, 10.0]])
    mask = torch.tensor([[True, True, True]])

    metrics = torch_metrics(prediction, target, mask.bool())

    assert metrics["samples"] == 3
    assert metrics["rmse"] == pytest.approx(np.sqrt(25.0 / 3.0))
    assert metrics["mae"] == pytest.approx((0.0 + 0.0 + 5.0) / 3.0)


def test_numpy_masked_metrics_matches():
    actual = np.array([1.0, 3.0, 10.0])
    predicted = np.array([1.0, 3.0, 5.0])
    mask = np.array([True, True, True])

    metrics = calculate_metrics(predicted, actual, mask)

    assert metrics["samples"] == 3
    assert metrics["rmse"] == pytest.approx(np.sqrt(25.0 / 3.0))
    assert metrics["mae"] == pytest.approx(5.0 / 3.0)


# ---------------------------------------------------------------------- #
# Baseline behaviour (trained on tiny synthetic data)
# ---------------------------------------------------------------------- #


def _synthetic_baseline_problem(n_windows=8):
    rng = np.random.RandomState(7)

    speed = 30.0 + rng.randn(n_windows, 100).cumsum(axis=1) * 0.5
    speed = np.maximum(speed, 0.0)

    x = rng.randn(n_windows, 100, 9).astype(np.float32)
    x = x + np.linspace(0.0, 1.0, 100)[None, :, None] * 0.05

    features = build_causal_features(x)
    mask = np.isfinite(speed)

    return features, speed.astype(np.float32), mask


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LinearRegressionBaseline(),
        lambda: RandomForestBaseline(seed=42),
    ],
)
def test_sklearn_baselines_fit_and_predict(factory):
    features, speed, mask = _synthetic_baseline_problem()

    baseline = factory()
    baseline.fit(
        features.reshape(-1, features.shape[-1]),
        speed.reshape(-1),
        mask.reshape(-1),
    )

    prediction = baseline.predict(features)
    assert prediction.shape == (8, 100)
    assert (prediction >= 0.0).all()

    metrics = calculate_metrics(speed, prediction, mask)
    assert metrics["rmse"] < 20.0


@pytest.mark.skipif(not _XGBOOST_AVAILABLE, reason="xgboost not installed")
def test_xgboost_baseline_fit_and_predict():
    features, speed, mask = _synthetic_baseline_problem()

    baseline = XGBoostBaseline(seed=42)
    baseline.fit(
        features.reshape(-1, features.shape[-1]),
        speed.reshape(-1),
        mask.reshape(-1),
    )

    prediction = baseline.predict(features)
    assert prediction.shape == (8, 100)
    assert (prediction >= 0.0).all()


def test_baseline_save_load_roundtrip(tmp_path):
    features, speed, mask = _synthetic_baseline_problem()

    baseline = LinearRegressionBaseline()
    baseline.fit(
        features.reshape(-1, features.shape[-1]),
        speed.reshape(-1),
        mask.reshape(-1),
    )

    path = tmp_path / "speed_baseline_linear.joblib"
    baseline.save(path)

    loaded = LinearRegressionBaseline.load(path)

    assert np.allclose(
        loaded.predict(features),
        baseline.predict(features),
    )


# ---------------------------------------------------------------------- #
# Runtime glue: CompositeMLInference + fallback
# ---------------------------------------------------------------------- #


def test_composite_ml_inference_speed_integration():
    from src.navigation.engine.model_interface import (
        CompositeMLInference,
        TrainedSpeedModel,
    )

    speed_model = TrainedSpeedModel(
        model_path="speed_lstm.pt",
        scaler_path="speed_lstm_scaler.npz",
        repo_root=MODEL_DIR,
    )

    if not speed_model.available():
        pytest.skip("speed_lstm artifacts not present")

    ml_inference = CompositeMLInference(speed_model=speed_model)

    window = np.random.RandomState(3).randn(100, 9).astype(np.float32)

    output = ml_inference.evaluate(timestamp=1.5, window=window)

    assert output.speed_mps is not None
    assert output.speed_std_mps is not None
    assert output.speed_mps >= 0.0
    assert np.isfinite(output.speed_mps)


def test_trained_speed_model_degrade_on_bad_window():
    from src.navigation.engine.model_interface import TrainedSpeedModel

    speed_model = TrainedSpeedModel(
        model_path="speed_lstm.pt",
        scaler_path="speed_lstm_scaler.npz",
        repo_root=MODEL_DIR,
    )

    if not speed_model.available():
        pytest.skip("speed_lstm artifacts not present")

    # Wrong shape -> must return (None, None), never raise.
    speed, std = speed_model.predict_speed(np.zeros((50, 9), dtype=np.float32))
    assert speed is None and std is None


def test_build_ml_inference_fallback_when_disabled():
    from src.navigation.engine.model_interface import (
        FallbackMLInference,
        build_ml_inference,
    )

    assert isinstance(build_ml_inference(None), FallbackMLInference)
    assert isinstance(
        build_ml_inference({"enabled": False}),
        FallbackMLInference,
    )


def test_build_ml_inference_fallback_when_artifact_missing(tmp_path):
    from src.navigation.engine.model_interface import (
        FallbackMLInference,
        build_ml_inference,
    )

    missing = tmp_path / "nope.pt"
    assert missing.exists() is False

    inference = build_ml_inference(
        {
            "enabled": True,
            "model": "lstm",
            "model_path": str(missing / "speed_lstm.pt"),
            "scaler_path": str(missing / "speed_lstm_scaler.npz"),
        },
        repo_root=tmp_path,
    )

    assert isinstance(inference, FallbackMLInference)


# ---------------------------------------------------------------------- #
# Dataset column fallback (validation split without * _cal columns)
# ---------------------------------------------------------------------- #


def test_dataset_cal_column_fallback():
    validation_path = REPO_ROOT / "data" / "validation" / "sequences.parquet"

    if not validation_path.exists():
        pytest.skip("validation sequences not present")

    dataset = SpeedSequenceDataset(str(validation_path))

    assert len(dataset) > 0

    x, y, mask = dataset[0]

    assert x.shape == (100, 9)
    assert y.shape == (100,)
    assert mask.shape == (100,)
    assert mask.dtype == torch.bool


# ---------------------------------------------------------------------- #
# Dummy guard: train.py builds models from checkpoints
# ---------------------------------------------------------------------- #


def test_build_model_from_checkpoint():
    from src.models.speed_estimator.inference import (
        build_model_from_checkpoint,
    )

    model = build_model_from_checkpoint({"model_type": "tcn"})

    assert isinstance(model, SpeedTCN)