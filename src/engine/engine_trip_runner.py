"""Trip-level engine runner (D-S11 integration).

Feeds a calibrated trip dataframe (optionally a blackout-scenario dataframe)
through the ``IDREngine`` exactly like the online runtime, and returns the
resulting trajectory plus offline evaluation metrics.

The runner never leaks reference columns into the runtime; GNSS columns are
consumed only when they are finite (blackout masks make them NaN), and the
reference_* columns are used only for scoring afterwards.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.navigation.core.sensor_adapter import (
    NavigationSensorAdapter,
    ORIENTATION_QUATERNION_COLUMNS,
)
from src.navigation.core.math_utils import heading_compass_from_quaternion
from src.navigation.interfaces.messages import GNSSSample, IMUSample, NavigationState
from src.navigation.fusion.ekf import EKF
from src.navigation.fusion.ukf import UKF
from src.navigation.engine.idr_engine import IDREngine
from src.navigation.map_matching.map_loader import load_road_graph
from src.navigation.map_matching.map_matcher import MapMatcher

EARTH_RADIUS_M = 6_378_137.0

_FILTERS = {"ekf": EKF, "ukf": UKF}

#: Sensor channels consumed by the trained speed models, in training order.
ML_FEATURE_COLUMNS = [
    "accel_x_cal",
    "accel_y_cal",
    "accel_z_cal",
    "gyro_x_cal",
    "gyro_y_cal",
    "gyro_z_cal",
    "mag_x_cal",
    "mag_y_cal",
    "mag_z_cal",
]


def load_yaml(path) -> dict:
    """Load a YAML config, returning {} when it is missing or malformed."""
    import yaml

    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@dataclass
class EngineTripResult:
    trajectory: pd.DataFrame
    final_state: NavigationState

    # Reference scoring (None when the trip carries no reference columns).
    position_rmse_m: Optional[float] = None
    final_position_error_m: Optional[float] = None
    velocity_rmse_mps: Optional[float] = None
    heading_rmse_rad: Optional[float] = None


# ---------------------------------------------------------------------- #
# Config -> engine
# ---------------------------------------------------------------------- #


def build_engine(config: dict) -> IDREngine:
    """Build an ``IDREngine`` from fused navigation/fusion/map config dicts."""
    engine_cfg = config.get("engine", {})
    fusion_cfg = config.get("fusion", {})
    map_cfg = config.get("map_matching", {})

    filter_type = str(
        engine_cfg.get("filter_type", fusion_cfg.get("filter_type", "ekf"))
    ).lower()
    filter_factory = _FILTERS.get(filter_type, EKF)

    fusion = _build_fusion(filter_factory, fusion_cfg)

    # Map matching
    map_matcher = None
    geojson = config.get("geojson_path") or map_cfg.get("map_geojson")
    if map_cfg.get("enabled", False) and geojson:
        graph = load_road_graph(source_path=geojson)
        map_matcher = MapMatcher(
            graph=graph,
            candidate_radius_m=float(map_cfg.get("candidate_radius_m", 50.0)),
            max_candidates=int(map_cfg.get("max_candidates", 5)),
        )

    # AI/ML integration (D-S7): Trap into the trained speed model when the
    # config requests it and the artifact exists; otherwise the engine keeps
    # its classical fallback (unchanged behaviour).
    ml_inference = _build_ml_from_config(
        config.get("ml", {}),
    )

    return IDREngine(
        fusion=fusion,
        map_matcher=map_matcher,
        map_match_std_m=float(engine_cfg.get("map_match_std_m", 3.0)),
        ml_inference=ml_inference,
    )


def _build_ml_from_config(ml_cfg: dict):
    from src.navigation.engine.model_interface import (
        FallbackMLInference,
        build_ml_inference,
    )

    if not ml_cfg.get("enabled", False):
        return None

    repo_root = Path(__file__).resolve().parents[2]

    return build_ml_inference(ml_cfg, repo_root=repo_root)


def _build_fusion(filter_factory, fusion_cfg: dict):
    from src.navigation.fusion.gnss_ins_fusion import GNSSINSFusion

    return GNSSINSFusion(
        filter_factory=filter_factory,
        re_localize_inflation=float(fusion_cfg.get("re_localize_inflation", 0.5)),
    )


# ---------------------------------------------------------------------- #
# Sample construction
# ---------------------------------------------------------------------- #


def _to_imu_sample(row: pd.Series, adapter: NavigationSensorAdapter) -> Optional[IMUSample]:
    timestamp = pd.to_numeric(row.get("timestamp"), errors="coerce")
    if not np.isfinite(timestamp):
        return None
    timestamp = float(timestamp)

    gyro_z = pd.to_numeric(row.get("gyro_z"), errors="coerce")
    if not np.isfinite(gyro_z):
        return None

    gyro = (
        float(pd.to_numeric(row.get("gyro_x"), errors="coerce")),
        float(pd.to_numeric(row.get("gyro_y"), errors="coerce")),
        float(gyro_z),
    )

    accel_enu = adapter.acceleration_enu(row)

    ax, ay, az = 0.0, 0.0, 0.0
    for column, default in (("linear_accel_x", 0.0), ("linear_accel_y", 0.0), ("linear_accel_z", 0.0)):
        v = pd.to_numeric(row.get(column), errors="coerce")
        if np.isfinite(v):
            if column == "linear_accel_x":
                ax = float(v)
            elif column == "linear_accel_y":
                ay = float(v)
            else:
                az = float(v)

    heading = None
    if all(c in row.index for c in ORIENTATION_QUATERNION_COLUMNS):
        q = adapter.orientation_quaternion(row)
        if q is not None:
            heading = heading_compass_from_quaternion(q)

    return IMUSample(
        timestamp=timestamp,
        accelerometer=(ax, ay, az),
        gyroscope=gyro,
        linear_acceleration_enu=accel_enu,
        heading_rad=heading,
    )


def _to_gnss_sample(row: pd.Series) -> Optional[GNSSSample]:
    # Blackout masks may set gnss_available = False explicitly.
    if "gnss_available" in row.index:
        avail = pd.to_numeric(row.get("gnss_available"), errors="coerce")
        if np.isfinite(avail) and float(avail) < 0.5:
            return None

    latitude = pd.to_numeric(row.get("latitude_deg"), errors="coerce")
    longitude = pd.to_numeric(row.get("longitude_deg"), errors="coerce")
    if not (np.isfinite(latitude) and np.isfinite(longitude)):
        return None

    accuracy = pd.to_numeric(row.get("position_accuracy_m"), errors="coerce")
    accuracy = float(accuracy) if np.isfinite(accuracy) else 10.0

    speed = None
    speed_kmh = pd.to_numeric(row.get("speed_kmh"), errors="coerce")
    if np.isfinite(speed_kmh):
        speed = float(speed_kmh) / 3.6

    heading = None
    gps_heading_deg = pd.to_numeric(row.get("gps_heading_deg"), errors="coerce")
    if np.isfinite(gps_heading_deg):
        heading = math.radians(float(gps_heading_deg))

    sample_timestamp = pd.to_numeric(row.get("timestamp"), errors="coerce")
    if not np.isfinite(sample_timestamp):
        return None

    return GNSSSample(
        timestamp=float(sample_timestamp),
        latitude=float(latitude),
        longitude=float(longitude),
        accuracy=accuracy,
        speed=speed,
        heading=heading,
    )


# ---------------------------------------------------------------------- #
# Trip execution
# ---------------------------------------------------------------------- #


def run_trip(
    df: pd.DataFrame,
    config: dict | None = None,
    engine: IDREngine | None = None,
    gnss_enabled: bool = True,
) -> EngineTripResult:
    config = config or {}
    engine = engine or build_engine(config)

    engine_cfg = config.get("engine", {})

    if "timestamp" not in df.columns:
        raise KeyError("trip dataframe is missing a 'timestamp' column")

    data = df.copy()
    data["timestamp"] = pd.to_numeric(data["timestamp"], errors="coerce")
    data = data.sort_values("timestamp").reset_index(drop=True)
    data = data[data["timestamp"].notna()]

    if data.empty:
        raise ValueError("trip dataframe contains no valid timestamps")

    adapter = NavigationSensorAdapter()

    # ------------------------------------------------------------ #
    # ML window feeding (D-S7). When ml.enabled is true and the
    # engine carries a real MLInference, buffer the calibrated sensor
    # window and feed it through the trained speed model.
    # ------------------------------------------------------------ #
    ml_enabled = bool(config.get("ml", {}).get("enabled", False))
    ml_window_samples = int(config.get("ml", {}).get("window_samples", 100))

    if ml_enabled:
        from src.navigation.engine.model_interface import FallbackMLInference

        ml_active = not isinstance(engine.ml_inference, FallbackMLInference)
        print(
            f"[ML] enabled = {ml_enabled} | active (trained model) = {ml_active}"
        )
        print(
            f"[ML] using {type(engine.ml_inference).__name__} "
            f"(speed_model={getattr(engine.ml_inference, 'speed_model', None) is not None})"
        )
    else:
        ml_active = False

    ml_window = deque(maxlen=ml_window_samples)

    rows = []
    for _, row in data.iterrows():
        if gnss_enabled:
            gnss = _to_gnss_sample(row)
            if gnss is None:
                continue
        else:
            gnss = None

        imu = _to_imu_sample(row, adapter)
        if imu is None:
            continue

        if gnss_enabled and not engine.initialized:
            engine.initialize(gnss.latitude, gnss.longitude)
        elif not engine.initialized:
            engine.initialize()

        engine.update_imu(imu)

        if gnss is not None:
            engine.update_gnss(gnss)

        # --------------------------------------------------------
        # Trained speed-model inference (optional)
        # --------------------------------------------------------
        if ml_active:
            features = np.asarray(
                [
                    pd.to_numeric(row.get(column), errors="coerce")
                    for column in ML_FEATURE_COLUMNS
                ],
                dtype=np.float32,
            )
            features = np.nan_to_num(features)
            ml_window.append(features)

            if len(ml_window) == ml_window_samples:
                window = np.stack(ml_window)
                output = engine.ml_inference.evaluate(
                    float(imu.timestamp),
                    window,
                )
                engine.update_ml(output)

        if engine_cfg.get("apply_non_holonomic", True):
            engine.apply_non_holonomic_constraint()

        if engine_cfg.get("apply_zupt", True):
            speed = engine.state.velocity_east_mps ** 2
            speed = math.sqrt(speed + engine.state.velocity_north_mps ** 2)
            threshold = float(engine_cfg.get("zupt_speed_threshold_mps", 0.2))
            if speed < threshold:
                engine.apply_zupt()

        if engine_cfg.get("map_matching", {}).get("enabled", False):
            engine.update_map_match()

        output = engine.get_state_dict()
        output.pop("confidence", None)
        output.pop("position_error", None)
        output.pop("mode", None)

        row_out = _copy_runtime_columns(row)
        row_out.update(output)
        rows.append(row_out)

    if not rows:
        raise ValueError("engine produced no valid trajectory samples")

    trajectory = pd.DataFrame(rows)

    final = trajectory.iloc[-1]
    final_state = NavigationState(
        timestamp=float(final["timestamp"]),
        east_m=float(final["east_m"]),
        north_m=float(final["north_m"]),
        velocity_east_mps=float(final["velocity_east_mps"]),
        velocity_north_mps=float(final["velocity_north_mps"]),
        heading_rad=float(final["heading"]),
        latitude=final.get("latitude"),
        longitude=final.get("longitude"),
        position_error_m=0.0,
        confidence=0.0,
        mode="",
    )
    final_state.position_error_m = engine.state.position_error_m
    final_state.confidence = engine.state.confidence
    final_state.mode = engine.state.mode

    metrics = _evaluate(trajectory)

    return EngineTripResult(
        trajectory=trajectory,
        final_state=final_state,
        **metrics,
    )


def _copy_runtime_columns(row: pd.Series) -> dict:
    keep = [
        "timestamp",
        "latitude_deg",
        "longitude_deg",
        "speed_kmh",
        "gps_heading_deg",
        "position_accuracy_m",
        "gnss_available",
        "blackout_phase",
        "blackout_id",
        "reference_latitude_deg",
        "reference_longitude_deg",
        "reference_speed_kmh",
        "reference_heading_deg",
    ]
    return {c: row.get(c) for c in keep if c in row.index}


# ---------------------------------------------------------------------- #
# Offline evaluation
# ---------------------------------------------------------------------- #


def _evaluate(trajectory: pd.DataFrame) -> dict:
    position_errors = None
    velocity_errors = None
    heading_errors = None

    east = trajectory["east_m"].to_numpy(dtype=float)
    north = trajectory["north_m"].to_numpy(dtype=float)

    if {"reference_latitude_deg", "reference_longitude_deg"} <= set(trajectory.columns):
        ref_lat = pd.to_numeric(trajectory["reference_latitude_deg"], errors="coerce").to_numpy()
        ref_lon = pd.to_numeric(trajectory["reference_longitude_deg"], errors="coerce").to_numpy()

        valid = np.isfinite(ref_lat) & np.isfinite(ref_lon)
        if valid.any():
            lat0 = np.radians(ref_lat[valid][0]) if valid.any() else 0.0
            lon0 = np.radians(ref_lon[valid][0]) if valid.any() else 0.0

            ref_e, ref_n = _enu(ref_lat[valid], ref_lon[valid], lat0, lon0)
            est_e, est_n = east[valid], north[valid]
            position_errors = np.hypot(est_e - ref_e, est_n - ref_n)

    if "reference_speed_kmh" in trajectory.columns:
        ref_speed = pd.to_numeric(trajectory["reference_speed_kmh"], errors="coerce").to_numpy() / 3.6
        est_speed = trajectory["speed_mps"].to_numpy(dtype=float) if "speed_mps" in trajectory.columns else np.hypot(
            trajectory["velocity_east_mps"].to_numpy(dtype=float),
            trajectory["velocity_north_mps"].to_numpy(dtype=float),
        )
        valid = np.isfinite(ref_speed)
        if valid.any():
            velocity_errors = est_speed[valid] - ref_speed[valid]

    if "reference_heading_deg" in trajectory.columns and "heading" in trajectory.columns:
        ref_heading = np.radians(pd.to_numeric(trajectory["reference_heading_deg"], errors="coerce").to_numpy())
        est_heading = trajectory["heading"].to_numpy(dtype=float)
        valid = np.isfinite(ref_heading)
        if valid.any():
            heading_errors = _heading_error(est_heading[valid], ref_heading[valid])

    return {
        "position_rmse_m": _safe_rmse(position_errors),
        "final_position_error_m": (float(position_errors[-1]) if position_errors is not None and len(position_errors) > 0 else None),
        "velocity_rmse_mps": _safe_rmse(velocity_errors),
        "heading_rmse_rad": _safe_rmse(heading_errors),
    }


def _enu(lat, lon, lat0, lon0):
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    east = (lon_r - lon0) * np.cos(lat0) * EARTH_RADIUS_M
    north = (lat_r - lat0) * EARTH_RADIUS_M
    return east, north


def _heading_error(est, ref):
    err = est - ref
    return (err + np.pi) % (2.0 * np.pi) - np.pi


def _safe_rmse(values):
    if values is None:
        return None
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return None
    return float(np.sqrt(np.mean(values ** 2)))


# ---------------------------------------------------------------------- #
# Public convenience wrappers
# ---------------------------------------------------------------------- #


def run_dead_reckoning(df: pd.DataFrame, config: dict) -> EngineTripResult:
    """Pure dead reckoning: GNSS is used only for the initial position."""
    cfg = _deep_config(config)
    return run_trip(df, cfg, gnss_enabled=False)


def run_fusion(df: pd.DataFrame, config: dict) -> EngineTripResult:
    """EKF/UKF + GNSS fusion through the real outage/blackout columns."""
    return run_trip(df, _deep_config(config), gnss_enabled=True)


def run_map_matching(df: pd.DataFrame, config: dict, geojson_path) -> EngineTripResult:
    cfg = _deep_config(config)
    cfg.setdefault("engine", {})
    cfg["engine"].setdefault("map_matching", {"enabled": False})
    cfg["engine"]["map_matching"]["enabled"] = True
    cfg["geojson_path"] = str(geojson_path)
    cfg.setdefault("map_matching", {})
    cfg["map_matching"]["enabled"] = True
    return run_trip(df, cfg, gnss_enabled=True)


def _deep_config(config: dict) -> dict:
    import copy

    return copy.deepcopy(config or {})


def print_engine_report(result: EngineTripResult, title: str = "NAVIGATION ENGINE") -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print(f"Samples: {len(result.trajectory)}")

    def _fmt(value, suffix="", unit=""):
        if value is None:
            return "unavailable"
        return f"{value:.3f} {unit}"

    print(f"Position RMSE: {_fmt(result.position_rmse_m, unit='m')}")
    print(f"Final position error: {_fmt(result.final_position_error_m, unit='m')}")
    print(f"Velocity RMSE: {_fmt(result.velocity_rmse_mps, unit='m/s')}")
    print(f"Heading RMSE: {_fmt(result.heading_rmse_rad, unit='rad')}")
    print(f"Final mode: {result.final_state.mode}")
    print(f"Final confidence: {result.final_state.confidence:.3f}")
    print("=" * 60)