import type { PositioningStatus } from '@/types/position';

/**
 * GNSS health classification — pure, dependency-free, testable.
 *
 * The app is deliberately truthful here: when the fix goes stale or the
 * accuracy blows out, we say so. There is no fabricated "intelligent
 * positioning" fallback; the only fallback (IDR) is a future interface and is
 * never claimed to be active while it isn't.
 */

/** A fix older than this is considered lost. */
export const GNSS_LOST_THRESHOLD_MS = 12_000;
/** A fix with accuracy radius worse than this is considered degraded. */
export const GNSS_DEGRADED_ACCURACY_METERS = 60;
/** Grace window after regaining a fix before we report fully available again. */
export const GNSS_RECOVERY_GRACE_MS = 6_000;

export interface GnssHealthInput {
  /** Epoch ms of the most recent fix, or null if never fixed. */
  lastFixMillis: number | null;
  /** Horizontal accuracy radius in meters, or null when unknown. */
  accuracyMeters: number | null;
  /** "Now", injectable for tests. */
  now?: number;
}

export type ClassifiedGnssHealth = Exclude<PositioningStatus, 'recovering'>;

/** Classify a single fix into available/degraded/lost without transition state. */
export function classifyGnssHealth(input: GnssHealthInput): ClassifiedGnssHealth {
  const now = input.now ?? Date.now();
  if (input.lastFixMillis === null) {
    return 'lost';
  }
  const ageMs = now - input.lastFixMillis;
  if (ageMs > GNSS_LOST_THRESHOLD_MS) {
    return 'lost';
  }
  if (
    input.accuracyMeters === null ||
    input.accuracyMeters > GNSS_DEGRADED_ACCURACY_METERS
  ) {
    return 'degraded';
  }
  return 'available';
}

export interface GnssTransition {
  status: PositioningStatus;
  /** Injectable recovering-until deadline (epoch ms). */
  recoveringUntil: number | null;
}

/**
 * Apply the recovering-grace transition on top of a plain classification.
 *
 * When a fix comes back after being lost we report `recovering` until the
 * grace window elapses, then fall back to the plain classification.
 */
export function transitionGnssStatus(
  previous: PositioningStatus,
  classified: ClassifiedGnssHealth,
  now: number,
  recoveringUntil: number | null,
  recoveryGraceMs = GNSS_RECOVERY_GRACE_MS,
): GnssTransition {
  if (classified === 'lost') {
    return { status: 'lost', recoveringUntil: null };
  }

  if (previous === 'lost' || previous === 'recovering') {
    if (recoveringUntil !== null && now < recoveringUntil) {
      return { status: 'recovering', recoveringUntil };
    }
  }

  const nextGrace = previous === 'lost' ? now + recoveryGraceMs : null;
  if (nextGrace !== null) {
    return { status: 'recovering', recoveringUntil: nextGrace };
  }

  return { status: classified, recoveringUntil: null };
}