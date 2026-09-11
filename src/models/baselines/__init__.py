"""D-T1 classical baselines for smartphone speed estimation."""

from src.models.baselines.base import ClassicalSpeedBaseline
from src.models.baselines.linear_regression import LinearRegressionBaseline
from src.models.baselines.random_forest import RandomForestBaseline
from src.models.baselines.xgboost_model import XGBoostBaseline, _XGBOOST_AVAILABLE

__all__ = [
    "ClassicalSpeedBaseline",
    "LinearRegressionBaseline",
    "RandomForestBaseline",
    "XGBoostBaseline",
    "_XGBOOST_AVAILABLE",
]