"""XGBoost baseline for smartphone speed estimation (D-T1).

XGBoost is an optional dependency. When it is unavailable the class still
imports so callers can record an explicit FAILED/dependency status instead of
crashing.
"""

from src.models.baselines.base import ClassicalSpeedBaseline

try:
    from xgboost import XGBRegressor

    _XGBOOST_AVAILABLE = True
except ImportError:
    XGBRegressor = None
    _XGBOOST_AVAILABLE = False


class XGBoostBaseline(ClassicalSpeedBaseline):
    """Gradient-boosted tree regressor on causal per-timestep features."""

    name = "xgboost"

    def __init__(self, seed: int = 42):
        super().__init__()

        if XGBRegressor is None:
            raise RuntimeError(
                "XGBoost is not installed. Run: python -m pip install xgboost"
            )

        self.model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=seed,
            n_jobs=-1,
        )