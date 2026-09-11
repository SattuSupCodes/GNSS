from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from src.engine.ds2_runner import DS2Runner
from src.navigation.core.math_utils import wrap_angle

EARTH_RADIUS_M = 6_378_137.0


@dataclass
class DS2Evaluation:
    trajectory: pd.DataFrame

    position_rmse_m: Optional[float]
    final_position_error_m: Optional[float]
    max_position_error_m: Optional[float]

    velocity_mae_mps: Optional[float]
    velocity_rmse_mps: Optional[float]

    heading_mae_rad: Optional[float]
    heading_rmse_rad: Optional[float]

    estimated_distance_m: float
    reference_distance_m: Optional[float]

    skipped_samples: int


def _haversine_distance_m(
    lat1_deg,
    lon1_deg,
    lat2_deg,
    lon2_deg,
):
    lat1 = np.radians(np.asarray(lat1_deg, dtype=float))
    lat2 = np.radians(np.asarray(lat2_deg, dtype=float))

    dlat = lat2 - lat1
    dlon = np.radians(
        np.asarray(lon2_deg, dtype=float)
        - np.asarray(lon1_deg, dtype=float)
    )

    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2.0) ** 2
    )

    return 2.0 * EARTH_RADIUS_M * np.arcsin(
        np.sqrt(np.clip(a, 0.0, 1.0))
    )


def _heading_error_rad(
    estimated,
    reference,
):
    error = np.asarray(estimated) - np.asarray(reference)

    return (
        (error + np.pi) % (2.0 * np.pi)
    ) - np.pi


def _safe_rmse(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]

    if len(values) == 0:
        return None

    return float(
        np.sqrt(np.mean(values ** 2))
    )


def _safe_mae(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]

    if len(values) == 0:
        return None

    return float(
        np.mean(np.abs(values))
    )

def _gnss_to_local_enu(
    latitude_deg,
    longitude_deg,
):
    """
    Convert latitude/longitude to a local ENU frame.

    The first valid GNSS coordinate is the local origin (0, 0).
    This is used only for offline evaluation.
    """
    lat = np.asarray(latitude_deg, dtype=float)
    lon = np.asarray(longitude_deg, dtype=float)

    valid = np.isfinite(lat) & np.isfinite(lon)

    east = np.full_like(lat, np.nan, dtype=float)
    north = np.full_like(lat, np.nan, dtype=float)

    if not valid.any():
        return east, north

    first = np.flatnonzero(valid)[0]

    lat0 = np.radians(lat[first])
    lon0 = np.radians(lon[first])

    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    east[valid] = (
        (lon_rad[valid] - lon0)
        * np.cos(lat0)
        * EARTH_RADIUS_M
    )

    north[valid] = (
        (lat_rad[valid] - lat0)
        * EARTH_RADIUS_M
    )

    return east, north
def evaluate_ds2(
    df: pd.DataFrame,
    runner: Optional[DS2Runner] = None,
) -> DS2Evaluation:
    """
    Run D-S2 and evaluate it against available offline reference data.

    Runtime navigation itself never consumes reference_* columns.

    Supported reference position forms:

        reference_latitude_deg
        reference_longitude_deg

    or:

        reference_east_m
        reference_north_m

    Supported reference velocity:

        reference_speed_mps

    Supported reference heading:

        reference_heading_rad
    """

    runner = runner or DS2Runner()

    result = runner.run(df)

    trajectory = result.trajectory.copy()

    position_errors = None

  # ------------------------------------------------------------
# Reference position
# ------------------------------------------------------------

    position_errors = None

    n = min(len(trajectory), len(df))

    est_east = trajectory["east_m"].iloc[:n].to_numpy()
    est_north = trajectory["north_m"].iloc[:n].to_numpy()

    # Current calibrated-data interface:
    # latitude_deg / longitude_deg
    if (
        "latitude_deg" in df.columns
        and "longitude_deg" in df.columns
    ):
        ref_east, ref_north = _gnss_to_local_enu(
            pd.to_numeric(
                df["latitude_deg"].iloc[:n],
                errors="coerce",
            ).to_numpy(),
            pd.to_numeric(
                df["longitude_deg"].iloc[:n],
                errors="coerce",
            ).to_numpy(),
        )

        valid = (
            np.isfinite(est_east)
            & np.isfinite(est_north)
            & np.isfinite(ref_east)
            & np.isfinite(ref_north)
        )

        if valid.any():
            position_errors = np.hypot(
                est_east[valid] - ref_east[valid],
                est_north[valid] - ref_north[valid],
            )

    # Backwards-compatible reference ENU interface
    elif (
        "reference_east_m" in df.columns
        and "reference_north_m" in df.columns
    ):
        ref_east = pd.to_numeric(
            df["reference_east_m"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        ref_north = pd.to_numeric(
            df["reference_north_m"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        valid = (
            np.isfinite(est_east)
            & np.isfinite(est_north)
            & np.isfinite(ref_east)
            & np.isfinite(ref_north)
        )

        if valid.any():
            position_errors = np.hypot(
                est_east[valid] - ref_east[valid],
                est_north[valid] - ref_north[valid],
            )

    # ------------------------------------------------------------
    # Reference geographic position
    # ------------------------------------------------------------

    elif (
        "reference_latitude_deg" in df.columns
        and "reference_longitude_deg" in df.columns
        and "latitude_deg" in trajectory.columns
        and "longitude_deg" in trajectory.columns
    ):
        n = min(
            len(trajectory),
            len(df),
        )

        est_lat = pd.to_numeric(
            trajectory["latitude_deg"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        est_lon = pd.to_numeric(
            trajectory["longitude_deg"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        ref_lat = pd.to_numeric(
            df["reference_latitude_deg"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        ref_lon = pd.to_numeric(
            df["reference_longitude_deg"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        valid = (
            np.isfinite(est_lat)
            & np.isfinite(est_lon)
            & np.isfinite(ref_lat)
            & np.isfinite(ref_lon)
        )

        if valid.any():
            position_errors = _haversine_distance_m(
                est_lat[valid],
                est_lon[valid],
                ref_lat[valid],
                ref_lon[valid],
            )

    # ------------------------------------------------------------
    # Velocity evaluation
    # ------------------------------------------------------------
    velocity_errors = None

    if "speed_kmh" in df.columns:
        n = min(len(trajectory), len(df))

        estimated_speed = (
            trajectory["speed_mps"]
            .iloc[:n]
            .to_numpy()
        )

        reference_speed = (
            pd.to_numeric(
                df["speed_kmh"].iloc[:n],
                errors="coerce",
            ).to_numpy()
            / 3.6
        )

        valid = (
            np.isfinite(estimated_speed)
            & np.isfinite(reference_speed)
        )

        if valid.any():
            velocity_errors = (
                estimated_speed[valid]
                - reference_speed[valid]
            )

    elif "reference_speed_mps" in df.columns:
        n = min(len(trajectory), len(df))

        estimated_speed = (
            trajectory["speed_mps"]
            .iloc[:n]
            .to_numpy()
        )

        reference_speed = pd.to_numeric(
            df["reference_speed_mps"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        valid = (
            np.isfinite(estimated_speed)
            & np.isfinite(reference_speed)
        )

        if valid.any():
            velocity_errors = (
                estimated_speed[valid]
                - reference_speed[valid]
            )
        

    # ------------------------------------------------------------
    # Heading evaluation
    # ------------------------------------------------------------

    heading_errors = None

    if "gps_heading_deg" in df.columns:
        n = min(len(trajectory), len(df))

        estimated_heading = (
            trajectory["heading_rad"]
            .iloc[:n]
            .to_numpy()
        )

        gps_bearing_deg = pd.to_numeric(
            df["gps_heading_deg"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        # GNSS bearing and backend heading share the SAME convention:
        #   0 deg/rad   = North
        #   90 deg/π/2  = East
        #
        # No 90-degree offset is needed anymore (D-S2 now outputs compass
        # heading, not ENU yaw).
        reference_heading = np.radians(
            gps_bearing_deg
        )

        reference_heading = (
            reference_heading + np.pi
        ) % (2.0 * np.pi) - np.pi

        valid = (
            np.isfinite(estimated_heading)
            & np.isfinite(reference_heading)
        )

        # GNSS course is unreliable at very low speed.
        if "speed_kmh" in df.columns:
            speed = pd.to_numeric(
                df["speed_kmh"].iloc[:n],
                errors="coerce",
            ).to_numpy()

            valid &= np.isfinite(speed) & (speed >= 5.0)

        if valid.any():
            heading_errors = _heading_error_rad(
                estimated_heading[valid],
                reference_heading[valid],
            )

    elif "reference_heading_rad" in df.columns:
        n = min(len(trajectory), len(df))

        estimated_heading = (
            trajectory["heading_rad"]
            .iloc[:n]
            .to_numpy()
        )

        reference_heading = pd.to_numeric(
            df["reference_heading_rad"].iloc[:n],
            errors="coerce",
        ).to_numpy()

        valid = (
            np.isfinite(estimated_heading)
            & np.isfinite(reference_heading)
        )

        if valid.any():
            heading_errors = _heading_error_rad(
                estimated_heading[valid],
                reference_heading[valid],
            )
    # ------------------------------------------------------------
    # Distance
    # ------------------------------------------------------------

    if len(trajectory) > 1:
        de = np.diff(
            trajectory["east_m"].to_numpy()
        )

        dn = np.diff(
            trajectory["north_m"].to_numpy()
        )

        estimated_distance = float(
            np.sum(
                np.hypot(de, dn)
            )
        )
    else:
        estimated_distance = 0.0

    reference_distance = None

    if (
        "latitude_deg" in df.columns
        and "longitude_deg" in df.columns
    ):
        lat = pd.to_numeric(
            df["latitude_deg"],
            errors="coerce",
        ).to_numpy()

        lon = pd.to_numeric(
            df["longitude_deg"],
            errors="coerce",
        ).to_numpy()

        valid = np.isfinite(lat) & np.isfinite(lon)

        if valid.sum() > 1:
            valid_lat = lat[valid]
            valid_lon = lon[valid]

            distances = _haversine_distance_m(
                valid_lat[:-1],
                valid_lon[:-1],
                valid_lat[1:],
                valid_lon[1:],
            )

            reference_distance = float(
                np.nansum(distances)
            )

    elif (
        "reference_latitude_deg" in df.columns
        and "reference_longitude_deg" in df.columns
    ):
        lat = pd.to_numeric(
            df["reference_latitude_deg"],
            errors="coerce",
        ).to_numpy()

        lon = pd.to_numeric(
            df["reference_longitude_deg"],
            errors="coerce",
        ).to_numpy()

        valid = np.isfinite(lat) & np.isfinite(lon)

        if valid.sum() > 1:
            valid_lat = lat[valid]
            valid_lon = lon[valid]

            distances = _haversine_distance_m(
                valid_lat[:-1],
                valid_lon[:-1],
                valid_lat[1:],
                valid_lon[1:],
            )

            reference_distance = float(
                np.nansum(distances)
            )
    return DS2Evaluation(
        trajectory=trajectory,

        position_rmse_m=(
            _safe_rmse(position_errors)
            if position_errors is not None
            else None
        ),

        final_position_error_m=(
            float(position_errors[-1])
            if position_errors is not None
            and len(position_errors) > 0
            else None
        ),

        max_position_error_m=(
            float(np.nanmax(position_errors))
            if position_errors is not None
            and len(position_errors) > 0
            else None
        ),

        velocity_mae_mps=(
            _safe_mae(velocity_errors)
            if velocity_errors is not None
            else None
        ),

        velocity_rmse_mps=(
            _safe_rmse(velocity_errors)
            if velocity_errors is not None
            else None
        ),

        heading_mae_rad=(
            _safe_mae(heading_errors)
            if heading_errors is not None
            else None
        ),

        heading_rmse_rad=(
            _safe_rmse(heading_errors)
            if heading_errors is not None
            else None
        ),

        estimated_distance_m=estimated_distance,
        reference_distance_m=reference_distance,

        skipped_samples=result.skipped_samples,
    )


def print_ds2_report(
    evaluation: DS2Evaluation,
) -> None:
    print()
    print("=" * 60)
    print("D-S2 BASIC INERTIAL NAVIGATION")
    print("=" * 60)

    print(
        f"Samples: {len(evaluation.trajectory)}"
    )

    print(
        f"Skipped samples: "
        f"{evaluation.skipped_samples}"
    )

    print()

    print(
        f"Estimated distance: "
        f"{evaluation.estimated_distance_m:.3f} m"
    )

    if evaluation.reference_distance_m is not None:
        print(
            f"Reference distance: "
            f"{evaluation.reference_distance_m:.3f} m"
        )

    print()

    if evaluation.position_rmse_m is not None:
        print(
            f"Position RMSE: "
            f"{evaluation.position_rmse_m:.3f} m"
        )

        print(
            f"Final position error: "
            f"{evaluation.final_position_error_m:.3f} m"
        )

        print(
            f"Maximum position error: "
            f"{evaluation.max_position_error_m:.3f} m"
        )
    else:
        print(
            "Position evaluation: unavailable"
        )

    print()

    if evaluation.velocity_mae_mps is not None:
        print(
            f"Velocity MAE: "
            f"{evaluation.velocity_mae_mps:.3f} m/s"
        )

        print(
            f"Velocity RMSE: "
            f"{evaluation.velocity_rmse_mps:.3f} m/s"
        )
    else:
        print(
            "Velocity evaluation: unavailable"
        )

    print()

    if evaluation.heading_mae_rad is not None:
        print(
            f"Heading MAE: "
            f"{np.degrees(evaluation.heading_mae_rad):.3f} deg"
        )

        print(
            f"Heading RMSE: "
            f"{np.degrees(evaluation.heading_rmse_rad):.3f} deg"
        )
    else:
        print(
            "Heading evaluation: unavailable"
        )

    print("=" * 60)