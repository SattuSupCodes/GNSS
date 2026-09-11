"""Random Forest baseline for smartphone speed estimation (D-T1)."""

from sklearn.ensemble import RandomForestRegressor

from src.models.baselines.base import ClassicalSpeedBaseline


class RandomForestBaseline(ClassicalSpeedBaseline):
    """Random-forest regressor on causal per-timestep features."""

    name = "random_forest"

    def __init__(self, seed: int = 42):
        super().__init__()
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_features=1.0,
            random_state=seed,
            n_jobs=-1,
        )