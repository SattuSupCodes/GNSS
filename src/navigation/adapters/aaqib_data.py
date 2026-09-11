from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from src.navigation.interfaces.messages import (
    GNSSSample,
    IMUSample,
)
from src.calibration.phone_alignment import PhoneAligner


class AaqibNavigationAdapter:
    """
    Adapter between Aaqib's calibrated DataFrame and the navigation backend.

    Responsibilities:
        - consume Aaqib's calibrated output
        - convert gravity-compensated linear acceleration from device
          frame to ENU
        - expose calibrated/aligned IMU measurements
        - convert GNSS measurements into GNSSSample

    This class deliberately does NOT:
        - estimate gravity
        - calibrate sensors
        - perform phone alignment globally
        - train ML models
        - use reference_* columns

    Those responsibilities belong upstream.
    """

    def __init__(
        self,
        phone_aligner: PhoneAligner,
    ):
        self.phone_aligner = phone_aligner

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _finite_triplet(
        row: pd.Series,
        columns: Tuple[str, str, str],
    ) -> Optional[Tuple[float, float, float]]:
        values = []

        for column in columns:
            if column not in row.index:
                return None

            value = pd.to_numeric(
                row[column],
                errors="coerce",
            )

            if pd.isna(value):
                return None

            value = float(value)

            if not math.isfinite(value):
                return None

            values.append(value)

        return tuple(values)

    @staticmethod
    def _timestamp(row: pd.Series) -> float:
        value = pd.to_numeric(
            row["timestamp"],
            errors="coerce",
        )

        if pd.isna(value):
            raise ValueError("Invalid timestamp")

        timestamp = float(value)

        if not math.isfinite(timestamp):
            raise ValueError("Invalid timestamp")

        return timestamp

    # ------------------------------------------------------------------
    # Acceleration
    # ------------------------------------------------------------------

    def linear_acceleration_enu(
        self,
        row: pd.Series,
    ) -> Optional[Tuple[float, float]]:
        """
        Convert Aaqib's gravity-compensated linear acceleration
        from device frame into ENU.

        Source columns:
            linear_accel_x
            linear_accel_y
            linear_accel_z

        Returns:
            (east_acceleration, north_acceleration)
        """

        vector = self._finite_triplet(
            row,
            (
                "linear_accel_x",
                "linear_accel_y",
                "linear_accel_z",
            ),
        )

        if vector is None:
            return None

        aligned = self.phone_aligner.align_single(
            np.asarray(vector, dtype=float)
        )

        if not np.isfinite(aligned).all():
            return None

        east = float(aligned[0])
        north = float(aligned[1])

        return east, north

    # ------------------------------------------------------------------
    # IMU
    # ------------------------------------------------------------------

    def imu_sample(
        self,
        row: pd.Series,
    ) -> IMUSample:
        """
        Convert one calibrated DataFrame row into IMUSample.
        """

        timestamp = self._timestamp(row)

        accel = self._finite_triplet(
            row,
            ("accel_x", "accel_y", "accel_z"),
        )

        gyro = self._finite_triplet(
            row,
            ("gyro_x", "gyro_y", "gyro_z"),
        )

        if accel is None:
            raise ValueError(
                f"Missing/invalid accelerometer data at timestamp {timestamp}"
            )

        if gyro is None:
            raise ValueError(
                f"Missing/invalid gyroscope data at timestamp {timestamp}"
            )

        magnetometer = self._finite_triplet(
            row,
            ("mag_x", "mag_y", "mag_z"),
        )

        linear_accel_enu = self.linear_acceleration_enu(row)

        return IMUSample(
            timestamp=timestamp,
            accelerometer=accel,
            gyroscope=gyro,
            magnetometer=magnetometer,
            linear_acceleration_enu=linear_accel_enu,
        )

    # ------------------------------------------------------------------
    # GNSS
    # ------------------------------------------------------------------

    def gnss_sample(
        self,
        row: pd.Series,
    ) -> Optional[GNSSSample]:
        """
        Convert GNSS information from a DataFrame row.

        Returns None when GNSS is unavailable/invalid.
        """

        timestamp = self._timestamp(row)

        # Explicit availability flag takes precedence if present.
        if "gnss_available" in row.index:
            available = row["gnss_available"]

            if pd.isna(available):
                return None

            if not bool(available):
                return None

        required = (
            "latitude_deg",
            "longitude_deg",
            "position_accuracy_m",
        )

        for column in required:
            if column not in row.index:
                return None

        lat = pd.to_numeric(
            row["latitude_deg"],
            errors="coerce",
        )

        lon = pd.to_numeric(
            row["longitude_deg"],
            errors="coerce",
        )

        accuracy = pd.to_numeric(
            row["position_accuracy_m"],
            errors="coerce",
        )

        if pd.isna(lat) or pd.isna(lon) or pd.isna(accuracy):
            return None

        lat = float(lat)
        lon = float(lon)
        accuracy = float(accuracy)

        if not all(
            math.isfinite(value)
            for value in (lat, lon, accuracy)
        ):
            return None

        # GNSS speed: source is km/h.
        speed = None

        if "speed_kmh" in row.index:
            value = pd.to_numeric(
                row["speed_kmh"],
                errors="coerce",
            )

            if not pd.isna(value) and math.isfinite(float(value)):
                speed = float(value) / 3.6

        # GNSS course: source is degrees clockwise from North.
        heading = None

        if "gps_heading_deg" in row.index:
            value = pd.to_numeric(
                row["gps_heading_deg"],
                errors="coerce",
            )

            if not pd.isna(value) and math.isfinite(float(value)):
                heading = math.radians(float(value))
                heading = heading % (2.0 * math.pi)

        return GNSSSample(
            timestamp=timestamp,
            latitude=lat,
            longitude=lon,
            accuracy=accuracy,
            speed=speed,
            heading=heading,
        )