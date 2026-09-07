"""Navigation backend (Phase 1, ISRO SIH 2024 - Intelligent Dead Reckoning).

Conventions used across this package:

    * world frame is ENU (x East, y North, z Up)
    * ``heading`` is the compass bearing clockwise from North
      (0 = North, +pi/2 = East)
    * ``gyro_z`` positive = counter-clockwise (heading decreases)
"""

from __future__ import annotations

from src.navigation.interfaces.messages import (
    GNSSSample,
    IMUSample,
    MLNavigationOutput,
    NavigationState,
)
from src.navigation.fusion.ekf import EKF
from src.navigation.fusion.ukf import UKF
from src.navigation.fusion.gnss_ins_fusion import GNSSINSFusion
from src.navigation.fusion.state_model import (
    ANGLE_INDICES,
    IDX_E,
    IDX_N,
    IDX_VE,
    IDX_VN,
    IDX_HEADING,
    IDX_GYRO_BIAS,
    IDX_ACCEL_BIAS_E,
    IDX_ACCEL_BIAS_N,
    STATE_SIZE,
)
from src.navigation.health.gnss_health import GNSSHealthMonitor, GNSSMode
from src.navigation.constraints.non_holonomic import NonHolonomicConstraint
from src.navigation.confidence.confidence import ConfidenceEstimator
from src.navigation.confidence.position_error import (
    cep50_m,
    cep95_m,
    confidence_from_error,
    position_std_m,
    position_std_isotropic_m,
    radius_for_probability_m,
)
from src.navigation.engine.idr_engine import IDREngine
from src.navigation.engine.model_interface import (
    FallbackMLInference,
    MLInference,
)
from src.navigation.map_matching.map_matcher import MapMatcher, RoadCandidate

__all__ = [
    "GNSSSample",
    "IMUSample",
    "MLNavigationOutput",
    "NavigationState",
    "EKF",
    "UKF",
    "GNSSINSFusion",
    "ANGLE_INDICES",
    "STATE_SIZE",
    "IDX_E",
    "IDX_N",
    "IDX_VE",
    "IDX_VN",
    "IDX_HEADING",
    "IDX_GYRO_BIAS",
    "IDX_ACCEL_BIAS_E",
    "IDX_ACCEL_BIAS_N",
    "GNSSHealthMonitor",
    "GNSSMode",
    "NonHolonomicConstraint",
    "ConfidenceEstimator",
    "cep50_m",
    "cep95_m",
    "confidence_from_error",
    "position_std_m",
    "position_std_isotropic_m",
    "radius_for_probability_m",
    "IDREngine",
    "FallbackMLInference",
    "MLInference",
    "MapMatcher",
    "RoadCandidate",
]