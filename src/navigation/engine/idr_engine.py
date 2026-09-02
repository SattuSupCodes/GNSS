import math
from navigation.interfaces.messages import IMUSample, GNSSSample, MLNavigationOutput, NavigationState
from navigation.core.math_utils import LocalENU, heading_from_velocity
from navigation.ins.orientation import OrientationEstimator
from navigation.fusion.ekf import EKF
from navigation.health.gnss_health import GNSSHealthMonitor, GNSSMode
from navigation.constraints.non_holonomic import NonHolonomicConstraint
from navigation.map_matching.map_matcher import MapMatcher
from navigation.confidence.confidence import ConfidenceEstimator

class IDREngine:
    """Public facade for the Phase 1 intelligent dead-reckoning backend."""
    def __init__(self, health=None, ekf=None, map_matcher=None, confidence=None, constraints=None):
        self.health = health or GNSSHealthMonitor()
        self.ekf = ekf or EKF()
        self.map_matcher = map_matcher or MapMatcher()
        self.confidence = confidence or ConfidenceEstimator()
        self.constraints = constraints or NonHolonomicConstraint()
        self.orientation = OrientationEstimator()
        self.origin: LocalENU | None = None
        self.initialized = False
        self.last_imu_timestamp = None
        self.last_gnss_timestamp = None
        self.mode = "UNINITIALIZED"
        self._state = NavigationState()

    def initialize(self, latitude=None, longitude=None, heading_rad=0.0):
        if latitude is not None and longitude is not None:
            self.origin = LocalENU(latitude, longitude)
        self.ekf.initialize(0.0, 0.0, heading_rad)
        self.initialized = True
        self.mode = "DEAD_RECKONING"
        self._refresh_state(0.0)

    def _ensure_initialized(self, gnss=None):
        if self.initialized:
            return
        if gnss is not None:
            self.initialize(gnss.latitude, gnss.longitude, gnss.heading or 0.0)
        else:
            self.initialize()

    def update_imu(self, sample: IMUSample):
        self._ensure_initialized()
        if self.last_imu_timestamp is None:
            dt = 0.0
        else:
            dt = sample.timestamp - self.last_imu_timestamp
        self.last_imu_timestamp = sample.timestamp
        if dt <= 0.0:
            return self.get_state()

        if sample.heading_rad is not None:
            heading = sample.heading_rad
        else:
            heading = self.orientation.update(sample.gyroscope[2], sample.magnetometer, dt)

        # Preferred: Aaqib's calibrated world-frame linear acceleration.
        if sample.linear_acceleration_enu is not None:
            accel_enu = sample.linear_acceleration_enu
        else:
            # Minimal fallback: treat x/y body acceleration as ENU after yaw rotation.
            # For production use, preprocessing/calibration should provide the ENU field.
            ax, ay, az = sample.accelerometer
            import numpy as np
            c, s = math.cos(heading), math.sin(heading)
            accel_enu = (c * ax - s * ay, s * ax + c * ay)

        self.ekf.predict(accel_enu, sample.gyroscope[2], dt)
        if self.health.mode in (GNSSMode.UNAVAILABLE, GNSSMode.RECOVERING):
            self.mode = "DEAD_RECKONING"
        elif self.health.mode == GNSSMode.DEGRADED:
            self.mode = "GNSS_INS_DEGRADED"
        else:
            self.mode = "GNSS_INS_FUSION"
        self._refresh_state(sample.timestamp)
        return self.get_state()

    def update_gnss(self, sample: GNSSSample):
        self._ensure_initialized(sample)
        if self.origin is None:
            self.origin = LocalENU(sample.latitude, sample.longitude)
        east, north = self.origin.to_xy(sample.latitude, sample.longitude)
        predicted = self.ekf.x[:2]
        innovation_m = math.hypot(east - predicted[0], north - predicted[1])
        health = self.health.update(sample.accuracy, sample.timestamp, innovation_m)
        # Even degraded GNSS can be useful; unavailable/jump measurements are rejected.
        if health != GNSSMode.UNAVAILABLE:
            self.ekf.update_gnss_position(east, north, sample.accuracy)
            if sample.speed is not None:
                self.ekf.update_speed(sample.speed, max(sample.accuracy * 0.1, 0.5))
            if sample.heading is not None and sample.speed is not None and sample.speed > 1.0:
                self.ekf.update_heading(sample.heading, 0.35 if health == GNSSMode.DEGRADED else 0.2)
        self.last_gnss_timestamp = sample.timestamp
        self.mode = {
            GNSSMode.HEALTHY: "GNSS_INS_FUSION",
            GNSSMode.DEGRADED: "GNSS_INS_DEGRADED",
            GNSSMode.RECOVERING: "RECOVERING",
            GNSSMode.UNAVAILABLE: "DEAD_RECKONING",
        }[health]
        self._refresh_state(sample.timestamp)
        return self.get_state()

    def update_ml(self, output: MLNavigationOutput):
        self._ensure_initialized()
        if output.speed_mps is not None:
            self.ekf.update_speed(output.speed_mps, output.speed_std_mps or 1.0)
        if output.heading_rad is not None:
            self.ekf.update_heading(output.heading_rad, output.heading_std_rad or 0.35)
        self._refresh_state(output.timestamp)
        return self.get_state()

    def apply_non_holonomic_constraint(self):
        self.constraints.apply(self.ekf, self.ekf.x[4])
        self._refresh_state(self._state.timestamp)
        return self.get_state()

    def get_state(self) -> NavigationState:
        return self._state

    def _refresh_state(self, timestamp):
        s = self.ekf.to_state(timestamp)
        if self.origin is not None:
            s.latitude, s.longitude = self.origin.to_ll(s.east_m, s.north_m)
        s.position_error_m = self.ekf.position_std_m
        s.confidence = self.confidence.estimate(s.position_error_m, self.mode)
        s.mode = self.mode
        self._state = s
