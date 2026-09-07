import numpy as np
import pandas as pd

from src.calibration.phone_alignment import PhoneAligner
from src.navigation.core.sensor_adapter import NavigationSensorAdapter
import pandas as pd

from src.engine.ds2_runner import DS2Runner

def test_navigation_sensor_adapter_preserves_dataframe():
    df = pd.DataFrame(
        {
            "timestamp": [1.0, 2.0],
            "linear_accel_x": [1.0, 2.0],
            "linear_accel_y": [0.0, 0.0],
            "linear_accel_z": [0.0, 0.0],
        }
    )

    aligner = PhoneAligner.from_preset(
        "TOP_NORTH_SCREEN_UP"
    )

    adapter = NavigationSensorAdapter(aligner)
    result = adapter.transform_dataframe(df)

    assert len(result) == 2

    assert "timestamp" in result.columns

    assert "linear_accel_x" in result.columns
    assert "linear_accel_y" in result.columns
    assert "linear_accel_z" in result.columns

    assert "linear_accel_x_aligned" in result.columns
    assert "linear_accel_y_aligned" in result.columns
    assert "linear_accel_z_aligned" in result.columns


def test_navigation_sensor_adapter_identity_alignment():
    df = pd.DataFrame(
        {
            "linear_accel_x": [1.0],
            "linear_accel_y": [2.0],
            "linear_accel_z": [3.0],
        }
    )

    aligner = PhoneAligner.from_preset(
        "TOP_NORTH_SCREEN_UP"
    )

    adapter = NavigationSensorAdapter(aligner)

    result = adapter.transform_dataframe(df)

    np.testing.assert_allclose(
        result[
            [
                "linear_accel_x_aligned",
                "linear_accel_y_aligned",
                "linear_accel_z_aligned",
            ]
        ].iloc[0].to_numpy(),
        [1.0, 2.0, 3.0],
        atol=1e-9,
    )


def test_navigation_sensor_adapter_extracts_horizontal_enu():
    aligner = PhoneAligner.from_preset(
        "TOP_NORTH_SCREEN_UP"
    )

    adapter = NavigationSensorAdapter(aligner)

    row = pd.Series(
        {
            "linear_accel_x": 1.5,
            "linear_accel_y": -2.0,
            "linear_accel_z": 0.25,
        }
    )

    acceleration = adapter.acceleration_enu(row)

    assert acceleration is not None

    np.testing.assert_allclose(
        acceleration,
        [1.5, -2.0],
        atol=1e-9,
    )


def test_navigation_sensor_adapter_rejects_missing_linear_acceleration():
    df = pd.DataFrame(
        {
            "timestamp": [1.0],
            "accel_x": [1.0],
            "accel_y": [2.0],
            "accel_z": [3.0],
        }
    )

    aligner = PhoneAligner.from_preset(
        "TOP_NORTH_SCREEN_UP"
    )

    adapter = NavigationSensorAdapter(aligner)

    try:
        adapter.transform_dataframe(df)
    except KeyError:
        pass
    else:
        raise AssertionError(
            "Expected KeyError for missing linear_accel_* columns"
        )
def test_ds2_runner_stationary_acceleration():
    import numpy as np
    import pandas as pd

    from src.calibration.phone_alignment import PhoneAligner
    from src.engine.ds2_runner import DS2Runner

    timestamps = np.arange(0.0, 1.0, 0.1)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "linear_accel_x": np.zeros(len(timestamps)),
            "linear_accel_y": np.zeros(len(timestamps)),
            "linear_accel_z": np.zeros(len(timestamps)),
            "gyro_z": np.zeros(len(timestamps)),
        }
    )

    runner = DS2Runner(
        aligner=PhoneAligner.from_preset(
            "TOP_NORTH_SCREEN_UP"
        )
    )

    result = runner.run(df)

    assert len(result.trajectory) == len(df)
    assert result.skipped_samples == 0

    assert abs(result.final_state.east_m) < 1e-9
    assert abs(result.final_state.north_m) < 1e-9

    assert abs(
        result.final_state.velocity_east_mps
    ) < 1e-9

    assert abs(
        result.final_state.velocity_north_mps
    ) < 1e-9


def test_ds2_runner_constant_north_acceleration():
    import numpy as np
    import pandas as pd

    from src.calibration.phone_alignment import PhoneAligner
    from src.engine.ds2_runner import DS2Runner

    timestamps = np.arange(0.0, 2.0, 0.1)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "linear_accel_x": np.zeros(len(timestamps)),
            "linear_accel_y": np.ones(len(timestamps)),
            "linear_accel_z": np.zeros(len(timestamps)),
            "gyro_z": np.zeros(len(timestamps)),
        }
    )

    runner = DS2Runner(
        aligner=PhoneAligner.from_preset(
            "TOP_NORTH_SCREEN_UP"
        )
    )

    result = runner.run(df)

    # With TOP_NORTH_SCREEN_UP the configured alignment
    # is identity, so device +Y is ENU +North.
    assert result.final_state.north_m > 0.0

    assert abs(
        result.final_state.east_m
    ) < 1e-6

    assert result.final_state.velocity_north_mps > 0.0


def test_ds2_runner_rejects_missing_columns():
    

    df = pd.DataFrame(
        {
            "timestamp": [0.0, 0.1],
        }
    )

    runner = DS2Runner()

    try:
        runner.run(df)
    except KeyError as exc:
        assert "linear_accel_x" in str(exc)
    else:
        raise AssertionError(
            "Expected KeyError for missing D-S2 columns"
        )


def test_ds2_runner_does_not_use_gnss_for_propagation():
    import numpy as np
    import pandas as pd

    from src.engine.ds2_runner import DS2Runner

    timestamps = np.arange(0.0, 1.0, 0.1)

    base = pd.DataFrame(
        {
            "timestamp": timestamps,
            "linear_accel_x": np.zeros(len(timestamps)),
            "linear_accel_y": np.ones(len(timestamps)),
            "linear_accel_z": np.zeros(len(timestamps)),
            "gyro_z": np.zeros(len(timestamps)),
        }
    )

    with_gnss = base.copy()

    with_gnss["latitude_deg"] = 28.6
    with_gnss["longitude_deg"] = 77.2
    with_gnss["speed_kmh"] = 999.0
    with_gnss["gps_heading_deg"] = 123.0

    runner_1 = DS2Runner()
    runner_2 = DS2Runner()

    result_1 = runner_1.run(base)
    result_2 = runner_2.run(with_gnss)

    assert np.isclose(
        result_1.final_state.east_m,
        result_2.final_state.east_m,
    )

    assert np.isclose(
        result_1.final_state.north_m,
        result_2.final_state.north_m,
    )

    assert np.isclose(
        result_1.final_state.velocity_east_mps,
        result_2.final_state.velocity_east_mps,
    )

    assert np.isclose(
        result_1.final_state.velocity_north_mps,
        result_2.final_state.velocity_north_mps,
    )
def test_ds2_evaluation_runs_without_reference():
    import numpy as np
    import pandas as pd

    from src.engine.ds2_evaluation import evaluate_ds2

    timestamps = np.arange(0.0, 2.0, 0.1)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "linear_accel_x": np.zeros(len(timestamps)),
            "linear_accel_y": np.zeros(len(timestamps)),
            "linear_accel_z": np.zeros(len(timestamps)),
            "gyro_z": np.zeros(len(timestamps)),
        }
    )

    evaluation = evaluate_ds2(df)

    assert evaluation.trajectory is not None
    assert len(evaluation.trajectory) == len(df)

    assert evaluation.position_rmse_m is None
    assert evaluation.velocity_rmse_mps is None
    assert evaluation.heading_rmse_rad is None


def test_ds2_evaluation_constant_motion():
    import numpy as np
    import pandas as pd

    from src.engine.ds2_evaluation import evaluate_ds2

    timestamps = np.arange(0.0, 2.0, 0.1)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "linear_accel_x": np.zeros(len(timestamps)),
            "linear_accel_y": np.ones(len(timestamps)),
            "linear_accel_z": np.zeros(len(timestamps)),
            "gyro_z": np.zeros(len(timestamps)),
        }
    )

    evaluation = evaluate_ds2(df)

    assert evaluation.estimated_distance_m > 0.0
    assert evaluation.position_rmse_m is None


def test_heading_error_wraps_correctly():
    import numpy as np

    from src.engine.ds2_evaluation import _heading_error_rad

    error = _heading_error_rad(
        np.array([np.deg2rad(179.0)]),
        np.array([np.deg2rad(-179.0)]),
    )

    assert np.isclose(
        np.degrees(error[0]),
        -2.0,
        atol=1e-6,
    )