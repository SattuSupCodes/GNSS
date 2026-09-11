from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from src.navigation.core.sensor_adapter import NavigationSensorAdapter
from src.navigation.ins.ins import InertialNavigator
from src.navigation.core.math_utils import heading_compass_from_quaternion
from src.navigation.interfaces.messages import NavigationState


@dataclass
class DS2RunResult:
    trajectory: pd.DataFrame
    final_state: NavigationState
    skipped_samples: int


class DS2Runner:
    """
    D-S2: basic smartphone inertial navigation.

    Pipeline:

        calibrated linear acceleration
                    +
        device->world orientation quaternion
                    |
                    v
              ENU acceleration
                    |
                    v
             InertialNavigator
                    |
                    v
          position / velocity / heading
    """

    def __init__(
      self,
    aligner=None,
    sensor_adapter: Optional[NavigationSensorAdapter] = None,
    ins: Optional[InertialNavigator] = None,
    max_dt: float = 1.0,
    ):
        if sensor_adapter is not None:
                self.sensor_adapter = sensor_adapter
        else:
                if aligner is None:
                    from src.calibration.phone_alignment import PhoneAligner

                    aligner = PhoneAligner.from_preset(
                        "TOP_NORTH_SCREEN_UP"
                    )

                self.sensor_adapter = NavigationSensorAdapter(
                    aligner=aligner
                )

        self.ins = (
            ins
            if ins is not None
            else InertialNavigator(max_dt=max_dt)
        )

        self.max_dt = float(max_dt)

    # ------------------------------------------------------------------ #
    # Main runner                                                         #
    # ------------------------------------------------------------------ #

    def run(
        self,
        df: pd.DataFrame,
        initial_state: Optional[NavigationState] = None,
    ) -> DS2RunResult:

        required = [
            "timestamp",
            "linear_accel_x",
            "linear_accel_y",
            "linear_accel_z",
            "gyro_z",
        ]

        missing = [c for c in required if c not in df.columns]

        if missing:
            raise KeyError(
                f"D-S2 input is missing required columns: {missing}"
            )

        if df.empty:
            raise ValueError("D-S2 input dataframe is empty")

        data = df.copy()

        data["timestamp"] = pd.to_numeric(
            data["timestamp"],
            errors="coerce",
        )

        data = data.sort_values("timestamp").reset_index(drop=True)

        valid_timestamp = data["timestamp"].notna()

        if not valid_timestamp.any():
            raise ValueError("D-S2 input contains no valid timestamps")

        first_timestamp = float(
            data.loc[valid_timestamp, "timestamp"].iloc[0]
        )

        state = (
            initial_state
            if initial_state is not None
            else self._make_initial_state(first_timestamp)
        )

        trajectory_rows = []

        previous_timestamp: Optional[float] = None
        skipped_samples = 0

        for _, row in data.iterrows():

            timestamp = pd.to_numeric(
                row["timestamp"],
                errors="coerce",
            )

            if not np.isfinite(timestamp):
                skipped_samples += 1
                continue

            timestamp = float(timestamp)

            # ---------------------------------------------------------- #
            # First sample                                                 #
            # ---------------------------------------------------------- #

            if previous_timestamp is None:
                previous_timestamp = timestamp

                trajectory_rows.append(
                    self._state_to_row(
                        state=state,
                        timestamp=timestamp,
                        dt=0.0,
                        row=row,
                    )
                )

                continue

            # ---------------------------------------------------------- #
            # Time step                                                     #
            # ---------------------------------------------------------- #

            dt = timestamp - previous_timestamp

            if dt <= 0.0 or dt > self.max_dt:
                skipped_samples += 1
                previous_timestamp = timestamp
                continue

            previous_timestamp = timestamp

            # ---------------------------------------------------------- #
            # Gyroscope                                                    #
            # ---------------------------------------------------------- #

            gyro_z = pd.to_numeric(
                row["gyro_z"],
                errors="coerce",
            )

            if not np.isfinite(gyro_z):
                skipped_samples += 1
                continue

            gyro_z = float(gyro_z)

            # ---------------------------------------------------------- #
            # Device acceleration -> world ENU                            #
            # ---------------------------------------------------------- #

            acceleration_enu = self.sensor_adapter.acceleration_enu(row)

            if acceleration_enu is None:
                skipped_samples += 1
                continue

            # ---------------------------------------------------------- #
            # Orientation                                                   #
            # ---------------------------------------------------------- #

            quaternion = self.sensor_adapter.orientation_quaternion(row)

            if quaternion is not None:
                # Compass heading: 0 rad = North, +pi/2 = East (matches the
                # convention used across the navigation backend).
                heading_rad = heading_compass_from_quaternion(quaternion)
            else:
                # No attitude quaternion means we cannot reliably provide
                # a world-frame heading. Preserve the previous heading.
                heading_rad = state.heading_rad

            # ---------------------------------------------------------- #
            # INS propagation                                               #
            # ---------------------------------------------------------- #

            state = self.ins.propagate(
                state=state,
                acceleration_enu=acceleration_enu,
                heading_rad=heading_rad,
                gyro_z=gyro_z,
                dt=dt,
            )

            trajectory_rows.append(
                self._state_to_row(
                    state=state,
                    timestamp=timestamp,
                    dt=dt,
                    row=row,
                )
            )

        if not trajectory_rows:
            raise ValueError("D-S2 produced no valid trajectory samples")

        trajectory = pd.DataFrame(trajectory_rows)

        return DS2RunResult(
            trajectory=trajectory,
            final_state=state,
            skipped_samples=skipped_samples,
        )

    # ------------------------------------------------------------------ #
    # Initial state                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _make_initial_state(timestamp: float) -> NavigationState:
        return NavigationState(
            timestamp=timestamp,
            east_m=0.0,
            north_m=0.0,
            velocity_east_mps=0.0,
            velocity_north_mps=0.0,
            heading_rad=0.0,
            gyro_bias_radps=0.0,
            accel_bias_east_mps2=0.0,
            accel_bias_north_mps2=0.0,
        )

    # ------------------------------------------------------------------ #
    # Output                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _state_to_row(
        state: NavigationState,
        timestamp: float,
        dt: float,
        row: pd.Series,
    ) -> dict:

        velocity_east = float(state.velocity_east_mps)
        velocity_north = float(state.velocity_north_mps)

        speed = float(
            np.hypot(
                velocity_east,
                velocity_north,
            )
        )

        output = {
            "timestamp": float(timestamp),
            "dt": float(dt),

            "east_m": float(state.east_m),
            "north_m": float(state.north_m),

            "velocity_east_mps": velocity_east,
            "velocity_north_mps": velocity_north,

            "speed_mps": speed,
            "heading_rad": float(state.heading_rad),

            "gyro_bias_radps": float(state.gyro_bias_radps),

            "accel_bias_east_mps2": float(
                state.accel_bias_east_mps2
            ),
            "accel_bias_north_mps2": float(
                state.accel_bias_north_mps2
            ),
        }

        # Keep offline reference information alongside the trajectory.
        reference_columns = [
            "latitude_deg",
            "longitude_deg",
            "speed_kmh",
            "gps_heading_deg",
            "position_accuracy_m",
            "is_reference",
        ]

        for column in reference_columns:
            if column in row.index:
                output[column] = row[column]

        return output