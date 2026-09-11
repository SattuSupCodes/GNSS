import { bearingDegrees, haversineDistanceMeters, smoothHeadingDegrees } from '@/core/geo';
import type { GeoPosition } from '@/types/position';

/**
 * Heading resolver.
 *
 * Priority:
 *  1. GNSS course-over-ground, when the device is actually moving
 *     (speed ≥ 1.5 m/s and a heading is reported).
 *  2. Bearing of the last two fixes, when the device moved ≥ 5 m recently.
 *  3. Compass (magnetometer) reading, smoothed with a wrap-around EMA.
 *
 * Always degrades gracefully: returns { headingDeg: null, valid: false } when
 * no source is reliable.
 */

export const GNSS_COURSE_MIN_SPEED_MPS = 1.5;
export const COURSE_MIN_MOVEMENT_METERS = 5;
export const HEADING_EMA_ALPHA = 0.25;

export interface HeadingSnapshot {
  headingDeg: number | null;
  valid: boolean;
  source: 'course' | 'dead-reckoned-course' | 'compass' | 'none';
}

export class HeadingEstimator {
  private smoothedCompass: number | null = null;
  private previousPosition: GeoPosition | null = null;

  /** Feed raw magnetic compass degrees (true-north adjusted by the caller). */
  feedCompass(rawHeadingDeg: number): void {
    if (!Number.isFinite(rawHeadingDeg)) return;
    this.smoothedCompass = smoothHeadingDegrees(
      this.smoothedCompass,
      rawHeadingDeg,
      HEADING_EMA_ALPHA,
    );
  }

  getCompassHeading(): number | null {
    return this.smoothedCompass;
  }

  /**
   * Resolve the current heading from a fresh position fix. `position` may be
   * null (no fix) — the latest compass value is still usable as a fallback.
   */
  update(position: GeoPosition | null): HeadingSnapshot {
    if (position) {
      const moving = position.speed !== null && position.speed >= GNSS_COURSE_MIN_SPEED_MPS;
      if (moving && position.heading !== null && Number.isFinite(position.heading)) {
        this.smoothedCompass = null;
        this.previousPosition = position;
        return { headingDeg: position.heading, valid: true, source: 'course' };
      }

      const prev = this.previousPosition;
      if (prev) {
        const moved = haversineDistanceMeters(prev, position) >= COURSE_MIN_MOVEMENT_METERS;
        if (moved) {
          const bearing = bearingDegrees(prev, position);
          this.smoothedCompass = null;
          this.previousPosition = position;
          return { headingDeg: bearing, valid: true, source: 'dead-reckoned-course' };
        }
      }
      this.previousPosition = position;
    }

    if (this.smoothedCompass !== null) {
      return { headingDeg: this.smoothedCompass, valid: true, source: 'compass' };
    }

    return { headingDeg: null, valid: false, source: 'none' };
  }

  reset(): void {
    this.smoothedCompass = null;
    this.previousPosition = null;
  }
}

let shared: HeadingEstimator | null = null;

/** Process-wide singleton used by the navigation orchestrator. */
export function getHeadingEstimator(): HeadingEstimator {
  if (!shared) shared = new HeadingEstimator();
  return shared;
}

export function resetHeadingEstimator(): void {
  shared = null;
}