from dataclasses import dataclass
from typing import Optional, Tuple


Vec3 = Tuple[float, float, float]
Vec2 = Tuple[float, float]


@dataclass(frozen=True)
class IMUSample:
    """
    One smartphone IMU sample.

    The generic accelerometer/gyroscope/magnetometer fields retain the
    sensor-frame measurements.

    `linear_acceleration_enu`, when supplied, is the preferred input
    for navigation because it is:
        - gravity compensated
        - transformed into ENU
        - expressed in m/s^2

    Heading convention:
        0       = North
        +pi/2   = East
        pi      = South
        -pi/2   = West

    Timestamp:
        seconds
    """

    timestamp: float

    accelerometer: Vec3
    gyroscope: Vec3
    magnetometer: Optional[Vec3] = None

    # Preferred navigation acceleration.
    linear_acceleration_enu: Optional[Vec2] = None

    # Optional externally supplied heading.
    heading_rad: Optional[float] = None


@dataclass(frozen=True)
class GNSSSample:
    """
    Smartphone GNSS measurement.

    latitude / longitude:
        degrees

    accuracy:
        horizontal position accuracy in metres

    speed:
        m/s, if available

    heading:
        radians, clockwise from North, if available
    """

    timestamp: float
    latitude: float
    longitude: float
    accuracy: float

    speed: Optional[float] = None
    heading: Optional[float] = None


@dataclass(frozen=True)
class MLNavigationOutput:
    """
    Interface between the ML team and navigation backend.

    ML models may change internally without requiring changes to the
    navigation engine.
    """

    timestamp: float

    speed_mps: Optional[float] = None
    speed_std_mps: Optional[float] = None

    heading_rad: Optional[float] = None
    heading_std_rad: Optional[float] = None

    accel_correction_enu: Optional[Vec2] = None
    accel_correction_std_mps2: Optional[float] = None

    # Predicted navigation position error (m) from a learned error model
    # (D-T5). When present the engine uses it as a floor for the reported
    # position error / confidence during GNSS outages.
    position_error_m: Optional[float] = None


@dataclass
class NavigationState:
    """
    Current navigation solution.

    Internal position:
        east_m, north_m

    Internal velocity:
        velocity_east_mps, velocity_north_mps

    Heading:
        radians, clockwise from North

    Biases:
        gyro yaw bias and horizontal acceleration biases

    Geographic output:
        latitude / longitude

    Uncertainty:
        position_error_m

    Confidence:
        [0, 1]

    Mode:
        current navigation mode
    """

    timestamp: float = 0.0

    # Local ENU position.
    east_m: float = 0.0
    north_m: float = 0.0

    # ENU velocity.
    velocity_east_mps: float = 0.0
    velocity_north_mps: float = 0.0

    # Heading, clockwise from North.
    heading_rad: float = 0.0

    # Estimated yaw-axis gyro bias.
    gyro_bias_radps: float = 0.0

    # Horizontal acceleration biases.
    accel_bias_east_mps2: float = 0.0
    accel_bias_north_mps2: float = 0.0

    # Geographic position.
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Estimated horizontal position uncertainty.
    position_error_m: float = float("inf")

    # [0, 1]
    confidence: float = 0.0

    # Navigation mode.
    mode: str = "UNINITIALIZED"