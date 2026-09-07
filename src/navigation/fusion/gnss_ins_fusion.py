"""GNSS + INS fusion engine (D-S4, D-S6).

``GNSSINSFusion`` owns the navigation filter plus the GNSS health machine
and an ENU origin. It exposes a small method surface the higher-level
``IDREngine`` drives:

    predict_imu(...)          propagate the filter (INS prediction)
    update_gnss(...)          GNSS measurement updates + outage/recovery
    update_ml(...)            AI velocity/heading/accel corrections (D-S7)
    apply_lateral_constraint() / apply_zupt()   vehicle constraints (D-S9)

The filter can be either the EKF or UKF (``filter_factory``).

Modes returned are the engine-facing strings:

    GNSS_INS_FUSION | GNSS_INS_DEGRADED | RECOVERING | DEAD_RECKONING
"""

from __future__ import annotations

import math

from src.navigation.health.gnss_health import GNSSHealthMonitor, GNSSMode
from src.navigation.core.math_utils import LocalENU
from src.navigation.fusion.ekf import EKF
from src.navigation.fusion.ukf import UKF
from src.navigation.constraints.non_holonomic import NonHolonomicConstraint

_MODE_MAP = {
    GNSSMode.HEALTHY: "GNSS_INS_FUSION",
    GNSSMode.DEGRADED: "GNSS_INS_DEGRADED",
    GNSSMode.RECOVERING: "RECOVERING",
    GNSSMode.UNAVAILABLE: "DEAD_RECKONING",
}


class GNSSINSFusion:
    """Encapsulates the filter + GNSS-health + ENU origin for one solution."""

    def __init__(
        self,
        vehicle=None,
        health: GNSSHealthMonitor | None = None,
        origin: LocalENU | None = None,
        filter_factory=EKF,
        re_localize_inflation: float = 0.5,
    ):
        self.filter = vehicle if vehicle is not None else filter_factory()
        self.health = health if health is not None else GNSSHealthMonitor()
        self.origin = origin if origin is not None else LocalENU()
        self.filter_factory = filter_factory
        self.re_localize_inflation = float(re_localize_inflation)
        self.initialized = False
        self.last_gnss_timestamp: float | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        self.filter.reset()
        self.health.reset()
        self.origin.reset()
        self.initialized = False
        self.last_gnss_timestamp = None

    def initialize(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        heading_rad: float = 0.0,
        east: float = 0.0,
        north: float = 0.0,
    ) -> None:
        if latitude is not None and longitude is not None:
            self.origin.set_origin(latitude, longitude)
            east, north = 0.0, 0.0
        self.filter.initialize(east, north, heading_rad)
        self.initialized = True

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #

    def predict_imu(
        self,
        accel_enu,
        gyro_z: float,
        dt: float,
        timestamp: float | None = None,
    ) -> str:
        """Propagate INS. Returns the current navigation mode string."""
        if not self.initialized:
            return "UNINITIALIZED"

        if timestamp is not None:
            self.health.check_stale(timestamp)

        self.filter.predict(accel_enu, gyro_z, dt)
        return self.mode

    # ------------------------------------------------------------------ #
    # GNSS measurements
    # ------------------------------------------------------------------ #

    def update_gnss(
        self,
        latitude: float,
        longitude: float,
        accuracy: float,
        timestamp: float,
        speed: float | None = None,
        heading: float | None = None,
    ) -> tuple[str, bool, float]:
        """Apply a GNSS fix; returns ``(mode, accepted, innovation_m)``."""
        if not self.initialized:
            self.initialize(latitude, longitude)
        elif not self.origin.initialized:
            self.origin.set_origin(latitude, longitude)

        east, north = self.origin.to_xy(latitude, longitude)

        predicted = self.filter.x[:2]
        innovation_m = float(
            math.hypot(east - predicted[0], north - predicted[1])
        )

        health_mode = self.health.update(accuracy, timestamp, innovation_m)
        accepted = False

        if health_mode != GNSSMode.UNAVAILABLE:
            accepted = True

            # Soft re-localization: after an outage the position error may be
            # much larger than the reported accuracy. Inflate the measurement
            # uncertainty during RECOVERING so the filter is pulled towards
            # the fix without over-trusting it.
            if health_mode == GNSSMode.RECOVERING:
                accuracy = max(
                    float(accuracy),
                    self.re_localize_inflation * innovation_m,
                )

            self.filter.update_gnss_position(east, north, accuracy)

            if speed is not None and float(speed) >= 0.0:
                self.filter.update_speed(speed, max(float(accuracy) * 0.1, 0.5))

            if heading is not None and speed is not None and float(speed) > 1.0:
                h_std = 0.35 if health_mode == GNSSMode.DEGRADED else 0.2
                self.filter.update_heading(heading, h_std)

        self.last_gnss_timestamp = timestamp
        return self.mode, accepted, innovation_m

    def gnss_age(self, timestamp: float) -> float:
        """Seconds since the last accepted GNSS fix (``inf`` if none yet)."""
        if self.last_gnss_timestamp is None:
            return float("inf")
        return max(float(timestamp) - self.last_gnss_timestamp, 0.0)

    # ------------------------------------------------------------------ #
    # AI / ML corrections (D-S7)
    # ------------------------------------------------------------------ #

    def update_ml(
        self,
        speed_mps: float | None = None,
        speed_std_mps: float | None = None,
        heading_rad: float | None = None,
        heading_std_rad: float | None = None,
        accel_correction_enu=None,
        accel_correction_std_mps2: float | None = None,
    ) -> None:
        """Feed learned measurements into the filter."""
        if not self.initialized:
            return

        if speed_mps is not None and float(speed_mps) >= 0.0:
            self.filter.update_speed(
                float(speed_mps),
                speed_std_mps if speed_std_mps is not None else 1.0,
            )
        if heading_rad is not None:
            self.filter.update_heading(
                float(heading_rad),
                heading_std_rad if heading_std_rad is not None else 0.35,
            )
        if accel_correction_enu is not None:
            self.filter.update_accel_correction(
                accel_correction_enu,
                accel_correction_std_mps2
                if accel_correction_std_mps2 is not None
                else 1.0,
            )

    # ------------------------------------------------------------------ #
    # Constraints & external corrections
    # ------------------------------------------------------------------ #

    def apply_lateral_constraint(
        self,
        lateral_std_mps: float = 0.5,
    ) -> None:
        if self.initialized:
            NonHolonomicConstraint().apply(
                self.filter, self.filter.x[4], lateral_std_mps
            )

    def apply_zupt(self, zero_velocity_std_mps: float = 0.05) -> None:
        if self.initialized:
            NonHolonomicConstraint().apply_zupt(
                self.filter, zero_velocity_std_mps
            )

    def re_localize(
        self,
        east: float,
        north: float,
        std_m: float = 3.0,
    ) -> None:
        """Hard external correction (e.g. a reliable map-matched pose)."""
        if self.initialized:
            self.filter.update_gnss_position(east, north, std_m)

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #

    @property
    def mode(self) -> str:
        return _MODE_MAP.get(self.health.mode, "DEAD_RECKONING")

    def to_state(self, timestamp: float = 0.0):
        x = self.filter.to_state(timestamp)
        if self.origin.initialized:
            x.latitude, x.longitude = self.origin.to_ll(x.east_m, x.north_m)
        return x