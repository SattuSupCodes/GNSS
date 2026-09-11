"""GNSS outage state machine (D-S5).

Transitions:

    HEALTHY  ->  DEGRADED   (accuracy worsens beyond ``degraded_accuracy_m``)
    DEGRADED ->  UNAVAILABLE (accuracy hopeless, feed stale, or spoofed jump)
    UNAVAILABLE -> RECOVERING -> HEALTHY (good fixes after an outage)
    any state -> UNAVAILABLE   (``check_stale`` when the feed goes silent)

Recovery is handled through ``recovering_updates`` consecutive acceptable
(post-outage) fixes, so a single glitchy fix does not immediately flip the
system back to HEALTHY.
"""

from __future__ import annotations

from enum import Enum


class GNSSMode(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    RECOVERING = "RECOVERING"


class GNSSHealthMonitor:
    def __init__(
        self,
        degraded_accuracy_m: float = 10.0,
        unavailable_accuracy_m: float = 50.0,
        max_gap_s: float = 3.0,
        recovering_updates: int = 3,
    ):
        self.degraded_accuracy_m = float(degraded_accuracy_m)
        self.unavailable_accuracy_m = float(unavailable_accuracy_m)
        self.max_gap_s = float(max_gap_s)
        self.recovering_updates = int(recovering_updates)
        self.mode = GNSSMode.UNAVAILABLE
        self.last_timestamp: float | None = None
        self.recovery_count = 0
        self.sustained_spoofs = 0

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        self.mode = GNSSMode.UNAVAILABLE
        self.last_timestamp = None
        self.recovery_count = 0
        self.sustained_spoofs = 0

    # ------------------------------------------------------------------ #
    # Streaming updates
    # ------------------------------------------------------------------ #

    def update(
        self,
        accuracy_m: float,
        timestamp: float,
        innovation_m: float | None = None,
    ) -> GNSSMode:
        """Process one GNSS measurement; returns the updated mode."""
        accuracy_m = float(accuracy_m)
        timestamp = float(timestamp)

        gap = (
            float("inf")
            if self.last_timestamp is None
            else timestamp - self.last_timestamp
        )
        self.last_timestamp = timestamp

        # -------------------------------------------------------------- #
        # First fix ever
        # -------------------------------------------------------------- #
        if gap == float("inf"):
            self.mode = (
                GNSSMode.HEALTHY
                if accuracy_m < self.degraded_accuracy_m
                else GNSSMode.DEGRADED
            )
            self.recovery_count = 0
            return self.mode

        # -------------------------------------------------------------- #
        # Accuracy too poor to be useful
        # -------------------------------------------------------------- #
        if accuracy_m >= self.unavailable_accuracy_m:
            self.mode = GNSSMode.UNAVAILABLE
            self.recovery_count = 0
            return self.mode

        bad_gap = gap > self.max_gap_s
        bad_jump = (
            innovation_m is not None
            and float(innovation_m) > max(3.0 * accuracy_m, 20.0)
        )

        # Once a recovery is under way, fixes far from the (still-stale)
        # estimate are convergence pulls, not spoofs: the spoof guard must
        # stay disabled until the innovation drops back to a sane size.
        recovering = self.recovery_count > 0 or bad_gap

        if bad_gap:
            # First fix after a GNSS absence: re-acquisition (recovery),
            # even if the innovation is large.
            self.recovery_count = 1
            self.sustained_spoofs = 0
        elif recovering:
            # Mid-recovery: count every usable fix towards health.
            self.recovery_count += 1
        elif bad_jump:
            # Large innovation during continuous tracking (no preceding
            # outage) => plausible spurious fix. But a *persistent* large
            # innovation across several self-consistent fixes is a genuine
            # hard re-location (bridge/tunnel/LAAS switch): re-arm recovery
            # so the filter can be pulled back, instead of dead-locking in
            # dead-reckoning forever.
            self.sustained_spoofs += 1
            if self.sustained_spoofs >= self.recovering_updates:
                self.recovery_count = 1
                self.sustained_spoofs = 0
                self.mode = GNSSMode.RECOVERING
                return self.mode
            self.mode = GNSSMode.UNAVAILABLE
            self.recovery_count = 0
            return self.mode
        else:
            self.recovery_count = 0
            self.sustained_spoofs = 0

        if self.recovery_count > 0:
            if (
                not bad_jump
                and accuracy_m < self.degraded_accuracy_m
                and self.recovery_count >= self.recovering_updates
            ):
                self.mode = GNSSMode.HEALTHY
                self.recovery_count = 0
                self.sustained_spoofs = 0
            elif accuracy_m < self.degraded_accuracy_m:
                self.mode = GNSSMode.RECOVERING
            else:
                self.mode = GNSSMode.DEGRADED
            return self.mode

        if accuracy_m >= self.degraded_accuracy_m:
            self.mode = GNSSMode.DEGRADED
        else:
            self.mode = GNSSMode.HEALTHY

        return self.mode

    # ------------------------------------------------------------------ #
    # Staleness (feed went silent between samples)
    # ------------------------------------------------------------------ #

    def check_stale(
        self,
        timestamp: float,
        max_gap_s: float | None = None,
    ) -> GNSSMode:
        """Mark the GNSS source unavailable if it went silent.

        Called from IMU updates so that an interrupted feed is reflected in
        the navigation mode without waiting for a new GNSS sample.
        """
        gap_limit = self.max_gap_s if max_gap_s is None else float(max_gap_s)

        if self.last_timestamp is None:
            return self.mode

        gap = float(timestamp) - self.last_timestamp
        if gap > gap_limit:
            if self.mode != GNSSMode.UNAVAILABLE:
                self.mode = GNSSMode.UNAVAILABLE
                self.recovery_count = 0

        return self.mode