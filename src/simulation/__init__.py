"""GNSS blackout simulation for GNSS-denied evaluation data (Phase 3).

Public API:
    from src.simulation import apply_blackout, plan_blackout_intervals
    from src.simulation import build_scenarios
    from src.simulation import create_blackout_dataset
    from src.simulation import EvaluationConfig, BlackoutDataset, BlackoutResult
"""

from __future__ import annotations

from .blackout_dataset import BlackoutDataset, create_blackout_dataset
from .blackout_scenarios import BlackoutScenario, build_scenarios
from .config import EvaluationConfig
from .gnss_blackout import (
    GNSS_FIELDS,
    BlackoutImpossibleError,
    BlackoutInterval,
    BlackoutResult,
    apply_blackout,
    plan_blackout_intervals,
)

__all__ = [
    "GNSS_FIELDS",
    "BlackoutDataset",
    "BlackoutImpossibleError",
    "BlackoutInterval",
    "BlackoutResult",
    "BlackoutScenario",
    "EvaluationConfig",
    "apply_blackout",
    "build_scenarios",
    "create_blackout_dataset",
    "plan_blackout_intervals",
]