import numpy as np

class NonHolonomicConstraint:
    """Vehicle-motion constraint: lateral/vertical velocity should be small.

    The current 2-D engine only applies the lateral component as a pseudo-measurement.
    It is a correction hook, not a replacement for a calibrated vehicle/phone frame.
    """
    def apply(self, ekf, heading_rad: float, lateral_std_mps: float = 0.5):
        # Vehicle-frame lateral velocity for heading measured clockwise from North.
        ve, vn = ekf.x[2], ekf.x[3]
        # Forward = [sin(h), cos(h)], left/right perpendicular = [cos(h), -sin(h)].
        lateral = ve * np.cos(heading_rad) - vn * np.sin(heading_rad)
        H = np.zeros((1, 8))
        H[0,2] = np.cos(heading_rad)
        H[0,3] = -np.sin(heading_rad)
        ekf._update([0.0], [lateral], H, np.array([[max(lateral_std_mps, 0.05)**2]]))
