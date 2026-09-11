"""Linear Regression baseline for smartphone speed estimation (D-T1)."""

from sklearn.linear_model import LinearRegression

from src.models.baselines.base import ClassicalSpeedBaseline


class LinearRegressionBaseline(ClassicalSpeedBaseline):
    """Ordinary least-squares regressor on causal per-timestep features."""

    name = "linear_regression"

    def __init__(self):
        super().__init__()
        self.model = LinearRegression()