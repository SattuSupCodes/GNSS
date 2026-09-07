import math

import numpy as np
import pandas as pd
import pytest

from src.engine.ds2_runner import DS2Runner
from src.engine.ds2_evaluation import evaluate_ds2, print_ds2_report
from src.navigation.core.math_utils import heading_compass_from_quaternion


def make_trip_df(n=20, accel_y=1.0, gyro_z=0.0):
    ts = 1600000000.0 + np.arange(n) / 10.0
    return pd.DataFrame(
        {
            "timestamp": ts,
            "linear_accel_x": np.zeros(n),
            "linear_accel_y": np.full(n, accel_y),
            "linear_accel_z": np.zeros(n),
            "gyro_z": np.full(n, gyro_z),
            "orient_qw": np.ones(n),
            "orient_qx": np.zeros(n),
            "orient_qy": np.zeros(n),
            "orient_qz": np.zeros(n),
        }
    )


def test_runner_produces_trajectory():
    result = DS2Runner().run(make_trip_df())
    assert len(result.trajectory) == 20
    assert result.skipped_samples == 0
    assert "east_m" in result.trajectory.columns
    assert "north_m" in result.trajectory.columns
    assert result.final_state is not None


def test_acceleration_direction_respects_heading():
    # Forward is device +Y; identity quaternion => forward = North.
    result = DS2Runner().run(make_trip_df(accel_y=1.0))
    final = result.trajectory.iloc[-1]
    assert final["north_m"] > 1.0
    assert abs(final["east_m"]) < 1e-6
    assert abs(final["heading_rad"]) < 1e-9


def test_missing_required_columns_raise():
    with pytest.raises(KeyError):
        DS2Runner().run(pd.DataFrame({"timestamp": [1.0]}))


def test_quaternion_heading_uses_compass_convention():
    # Identity quaternion: device +Y forward => pointing North.
    q = np.array([1.0, 0.0, 0.0, 0.0])
    assert heading_compass_from_quaternion(q) == pytest.approx(0.0)

    # Pure yaw pi/2 about +Z (device x-axis toward East):
    # R = rotate(pi/2, z); device +Y -> world -X (West) => heading -pi/2.
    qz = np.array([math.cos(math.pi / 4), 0.0, 0.0, math.sin(math.pi / 4)])
    assert heading_compass_from_quaternion(qz) == pytest.approx(-math.pi / 2)


def test_evaluate_ds2_reports_metrics(capsys):
    df = make_trip_df(accel_y=0.5)
    df["latitude_deg"] = 52.5
    df["longitude_deg"] = -1.9
    df["reference_latitude_deg"] = 52.5 + np.cumsum(np.zeros(len(df)))
    df["reference_longitude_deg"] = -1.9
    df["gps_heading_deg"] = 0.0

    evaluation = evaluate_ds2(df)

    assert evaluation.position_rmse_m is not None
    assert evaluation.final_position_error_m is not None
    assert evaluation.estimated_distance_m >= 0.0

    print_ds2_report(evaluation)
    captured = capsys.readouterr()
    assert "Position RMSE" in captured.out