import math
import numpy as np
from navigation.core.math_utils import wrap_angle
from navigation.interfaces.messages import NavigationState

N = 8

class EKF:
    """Extended Kalman filter for the 2-D navigation state.

    x = [east, north, v_east, v_north, heading, gyro_bias, accel_bias_e, accel_bias_n]
    """
    def __init__(self):
        self.x = np.zeros(N, dtype=float)
        self.P = np.diag([25.0, 25.0, 4.0, 4.0, 0.25, 0.03**2, 0.5**2, 0.5**2])
        self.initialized = False

    def initialize(self, east=0.0, north=0.0, heading=0.0):
        self.x[:] = 0.0
        self.x[0], self.x[1], self.x[4] = east, north, heading
        self.initialized = True

    def _f(self, x, accel_enu, gyro_z, dt):
        y = x.copy()
        ae = accel_enu[0] - x[6]
        an = accel_enu[1] - x[7]
        omega = gyro_z - x[5]
        y[0] = x[0] + x[2] * dt + 0.5 * ae * dt * dt
        y[1] = x[1] + x[3] * dt + 0.5 * an * dt * dt
        y[2] = x[2] + ae * dt
        y[3] = x[3] + an * dt
        y[4] = wrap_angle(x[4] + omega * dt)
        return y

    def predict(self, accel_enu, gyro_z, dt):
        if not self.initialized or dt <= 0.0 or dt > 1.0:
            return
        old = self.x.copy()
        self.x = self._f(old, accel_enu, gyro_z, dt)
        # Numerical Jacobian keeps the first implementation easy to audit/modify.
        F = np.zeros((N, N))
        eps = 1e-6
        for i in range(N):
            xp = old.copy(); xm = old.copy()
            xp[i] += eps; xm[i] -= eps
            F[:, i] = (self._f(xp, accel_enu, gyro_z, dt) - self._f(xm, accel_enu, gyro_z, dt)) / (2 * eps)
        q = np.diag([
            0.01**2, 0.01**2,
            0.25**2, 0.25**2,
            0.02**2, 0.0005**2,
            0.01**2, 0.01**2,
        ]) * max(dt, 1e-3)
        self.P = F @ self.P @ F.T + q
        self.P = 0.5 * (self.P + self.P.T)

    def _update(self, z, h, H, R, angle_indices=()):
        innovation = np.asarray(z, dtype=float) - np.asarray(h, dtype=float)
        for i in angle_indices:
            innovation[i] = wrap_angle(float(innovation[i]))
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.pinv(S)
        self.x = self.x + K @ innovation
        self.x[4] = wrap_angle(self.x[4])
        I = np.eye(N)
        # Joseph form is numerically safer than (I-KH)P.
        self.P = (I - K @ H) @ self.P @ (I - K @ H).T + K @ R @ K.T
        self.P = 0.5 * (self.P + self.P.T)

    def update_gnss_position(self, east, north, accuracy_m):
        H = np.zeros((2, N)); H[0,0] = 1.0; H[1,1] = 1.0
        sigma = max(float(accuracy_m), 1.0)
        self._update([east, north], [self.x[0], self.x[1]], H, np.eye(2) * sigma**2)

    def update_speed(self, speed_mps, std_mps=1.0):
        speed = max(float(speed_mps), 0.0)
        v = self.x[2:4]
        norm = float(np.linalg.norm(v))
        if norm < 1e-4:
            # Speed = ||v|| has zero gradient at rest. Use the current heading as the
            # temporary direction so an AI speed measurement can initialize velocity.
            h = [0.0]
            H = np.zeros((1, N))
            H[0,2] = math.sin(self.x[4])
            H[0,3] = math.cos(self.x[4])
            self._update([speed], h, H, np.array([[max(float(std_mps), 0.1)**2]]))
        else:
            h = [norm]
            H = np.zeros((1, N)); H[0,2] = v[0]/norm; H[0,3] = v[1]/norm
            self._update([speed], h, H, np.array([[max(float(std_mps), 0.1)**2]]))

    def update_heading(self, heading_rad, std_rad=0.25):
        H = np.zeros((1, N)); H[0,4] = 1.0
        self._update([heading_rad], [self.x[4]], H, np.array([[max(float(std_rad), 0.01)**2]]), angle_indices=(0,))

    def to_state(self, timestamp=0.0):
        return NavigationState(
            timestamp=timestamp,
            east_m=float(self.x[0]), north_m=float(self.x[1]),
            velocity_east_mps=float(self.x[2]), velocity_north_mps=float(self.x[3]),
            heading_rad=float(self.x[4]), gyro_bias_radps=float(self.x[5]),
            accel_bias_east_mps2=float(self.x[6]), accel_bias_north_mps2=float(self.x[7]),
        )

    @property
    def position_std_m(self):
        return float(math.sqrt(max(self.P[0,0] + self.P[1,1], 0.0)))
