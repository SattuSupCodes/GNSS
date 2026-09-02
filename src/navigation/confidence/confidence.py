import math

class ConfidenceEstimator:
    def __init__(self, reference_error_m=10.0, minimum=0.0, maximum=1.0):
        self.reference_error_m = reference_error_m
        self.minimum = minimum
        self.maximum = maximum

    def estimate(self, position_std_m: float, mode: str) -> float:
        if not math.isfinite(position_std_m):
            return self.minimum
        # Smooth, monotonic mapping from estimated uncertainty to [0,1].
        c = math.exp(-position_std_m / max(self.reference_error_m, 1e-6))
        if mode == "HEALTHY":
            c = min(1.0, c * 1.05)
        elif mode == "DEAD_RECKONING":
            c *= 0.95
        return min(self.maximum, max(self.minimum, c))
