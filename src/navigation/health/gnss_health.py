from enum import Enum

class GNSSMode(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    RECOVERING = "RECOVERING"

class GNSSHealthMonitor:
    def __init__(self, degraded_accuracy_m=10.0, unavailable_accuracy_m=50.0, max_gap_s=3.0, recovering_updates=3):
        self.mode = GNSSMode.UNAVAILABLE
        self.degraded_accuracy_m = degraded_accuracy_m
        self.unavailable_accuracy_m = unavailable_accuracy_m
        self.max_gap_s = max_gap_s
        self.recovering_updates = recovering_updates
        self.last_timestamp = None
        self.recovery_count = 0

    def update(self, accuracy_m: float, timestamp: float, innovation_m: float | None = None) -> GNSSMode:
        accuracy_m = float(accuracy_m)
        gap = float("inf") if self.last_timestamp is None else timestamp - self.last_timestamp
        self.last_timestamp = timestamp
        if gap == float("inf"):
            self.mode = GNSSMode.HEALTHY if accuracy_m < self.degraded_accuracy_m else GNSSMode.DEGRADED
            self.recovery_count = 0
            return self.mode
        bad_gap = gap > self.max_gap_s
        bad_jump = innovation_m is not None and innovation_m > max(3.0 * accuracy_m, 20.0)
        if bad_gap or accuracy_m >= self.unavailable_accuracy_m or bad_jump:
            self.mode = GNSSMode.UNAVAILABLE
            self.recovery_count = 0
        elif accuracy_m >= self.degraded_accuracy_m:
            self.mode = GNSSMode.DEGRADED
            self.recovery_count = 0
        elif self.mode in (GNSSMode.UNAVAILABLE, GNSSMode.RECOVERING):
            self.recovery_count += 1
            if self.recovery_count >= self.recovering_updates:
                self.mode = GNSSMode.HEALTHY
            else:
                self.mode = GNSSMode.RECOVERING
        else:
            self.mode = GNSSMode.HEALTHY
        return self.mode
