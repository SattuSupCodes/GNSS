import math

import pandas as pd

from src.calibration.phone_alignment import PhoneAligner, get_preset
from src.navigation.adapters.aaqib_data import AaqibNavigationAdapter


def test_linear_acceleration_is_converted_to_enu():
    """
    TOP_NORTH_SCREEN_UP means:

        device X -> East
        device Y -> North
        device Z -> Up

    Therefore:
        [1, 0, 0] device acceleration
        -> [1, 0, 0] ENU acceleration.
    """

    aligner = PhoneAligner.from_preset(
        "TOP_NORTH_SCREEN_UP"
    )

    adapter = AaqibNavigationAdapter(aligner)

    row = pd.Series(
        {
            "timestamp": 1.0,

            "accel_x": 0.0,
            "accel_y": 0.0,
            "accel_z": 9.81,

            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0,

            "linear_accel_x": 1.0,
            "linear_accel_y": 2.0,
            "linear_accel_z": 0.0,
        }
    )

    result = adapter.linear_acceleration_enu(row)

    assert result is not None

    east, north = result

    assert math.isclose(east, 1.0, abs_tol=1e-6)
    assert math.isclose(north, 2.0, abs_tol=1e-6)


def test_gnss_speed_is_converted_from_kmh_to_mps():
    aligner = PhoneAligner.from_preset(
        "TOP_NORTH_SCREEN_UP"
    )

    adapter = AaqibNavigationAdapter(aligner)

    row = pd.Series(
        {
            "timestamp": 2.0,
            "latitude_deg": 28.6139,
            "longitude_deg": 77.2090,
            "position_accuracy_m": 3.0,
            "speed_kmh": 36.0,
            "gps_heading_deg": 90.0,
            "gnss_available": True,
        }
    )

    result = adapter.gnss_sample(row)

    assert result is not None

    assert math.isclose(
        result.speed,
        10.0,
        abs_tol=1e-6,
    )

    assert math.isclose(
        result.heading,
        math.pi / 2.0,
        abs_tol=1e-6,
    )


def test_unavailable_gnss_returns_none():
    aligner = PhoneAligner.from_preset(
        "TOP_NORTH_SCREEN_UP"
    )

    adapter = AaqibNavigationAdapter(aligner)

    row = pd.Series(
        {
            "timestamp": 2.0,
            "latitude_deg": 28.6139,
            "longitude_deg": 77.2090,
            "position_accuracy_m": 3.0,
            "gnss_available": False,
        }
    )

    assert adapter.gnss_sample(row) is None