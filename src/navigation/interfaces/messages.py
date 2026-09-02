from dataclasses import dataclass
from typing import Optional, Tuple


Vec3 = Tuple[float, float, float]
Vec2 = Tuple[float, float]


@dataclass(frozen=True)
class IMUSample:
    """
    One smartphone IMU sample.

    Coordinate convention
    ---------------------
    Raw accelerometer and gyroscope values are in the smartphone frame.

    We assume the phone is mounted aligned with the vehicle, so the
    phone-to-vehicle transformation is fixed rather than continuously
    estimated.

    Units:
        accelerometer: m/s^2
        gyroscope: rad/s
        magnetometer: arbitrary sensor units
        timestamp: seconds
    """

    timestamp: float

    accelerometer: Vec3
    gyroscope: Vec3

    magnetometer: Optional[Vec3] = None

    # Preferred input from preprocessing.
    # If supplied, this should already be gravity-compensated and expressed
    # in the local ENU navigation frame.
    linear_acceleration_enu: Optional[Vec2] = None

    # Optional externally estimated heading.
    # Convention:
    #   0 rad   = North
    #   pi/2    = East
    #   pi      = South
    #   -pi/2   = West
    heading_rad: Optional[float] = None


@dataclass(frozen=True)
class GNSSSample:
    """
    Smartphone GNSS measurement.

    latitude / longitude:
        degrees

    accuracy:
        reported horizontal position accuracy in metres

    speed:
        m/s, if available

    heading:
        radians, if available
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
    Interface between the ML team and the navigation backend.

    Tanishk's models can change internally without requiring changes to
    the navigation engine.

    speed_mps:
        estimated vehicle speed

    speed_std_mps:
        estimated standard deviation of the speed prediction

    heading_rad:
        optional learned heading

    heading_std_rad:
        uncertainty of learned heading

    accel_correction_enu:
        optional learned correction to ENU acceleration
    """

    timestamp: float

    speed_mps: Optional[float] = None
    speed_std_mps: Optional[float] = None

    heading_rad: Optional[float] = None
    heading_std_rad: Optional[float] = None

    accel_correction_enu: Optional[Vec2] = None


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

    Bias states:
        estimated sensor biases

    Output position:
        latitude / longitude

    Uncertainty:
        position_error_m

    confidence:
        [0, 1]

    mode:
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

    # Estimated gyro bias.
    gyro_bias_radps: float = 0.0

    # Estimated acceleration biases.
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