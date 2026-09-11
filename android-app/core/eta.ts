import type { Route } from '@/types/routing';
import type { RouteProgressSnapshot } from '@/types/navigation';

/**
 * ETA estimation — pure and testable.
 *
 * Blends two sources:
 *  - route-profile estimate: remaining route duration scaled by progress
 *  - live-speed estimate:     remaining distance / current speed
 *
 * When the user is nearly stationary the live-speed estimate collapses, so it
 * is only trusted above a minimum speed and the result is a weighted blend.
 */

export const MIN_TRUSTED_SPEED_MPS = 0.6;

export interface EtaInput {
  route: Route;
  progress: RouteProgressSnapshot;
  currentSpeedMps: number | null;
  now?: number;
}

export function estimateRemainingSeconds(input: EtaInput): number {
  const { progress, currentSpeedMps } = input;
  if (progress.arrived || progress.remainingDistanceMeters <= 0) return 0;

  const routeBased = progress.remainingDurationSeconds;
  if (currentSpeedMps === null || currentSpeedMps < MIN_TRUSTED_SPEED_MPS) {
    return routeBased;
  }

  const speedBased = progress.remainingDistanceMeters / currentSpeedMps;
  // Weighted toward the live estimate while moving, but never fully trusting
  // a single speed sample (GNSS speed jitters).
  return speedBased * 0.6 + routeBased * 0.4;
}

export function estimateArrivalMillis(remainingSeconds: number, now?: number): number {
  return (now ?? Date.now()) + remainingSeconds * 1000;
}

/** Estimate arrival epoch for a snapshot. */
export function estimateEtaMillis(input: EtaInput): number | null {
  const remaining = estimateRemainingSeconds(input);
  if (remaining <= 0) return null;
  return estimateArrivalMillis(remaining, input.now);
}

/** Friendly "h:mm AM/PM" from epoch ms. */
export function formatEtaTime(etaMillis: number | null): string {
  if (etaMillis === null) return '--';
  const date = new Date(etaMillis);
  let hours = date.getHours();
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const meridiem = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12 || 12;
  return `${hours}:${minutes} ${meridiem}`;
}

/** Friendly duration "Xm · Ys" / "Xh Ym" style. */
export function formatRemainingDuration(seconds: number | null): string {
  if (seconds === null) return '--';
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}