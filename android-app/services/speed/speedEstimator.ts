import type { PositionProvider } from '@/types/position';

/**
 * Speed estimation seam.
 *
 * Active implementation: GNSS speed (course over ground).
 * Future integration point (contract only): the ML speed model (Tanishk's
 * work) via MLSpeedEstimator, and a sensor-based fallback. Nothing here ever
 * fabricates a speed value — when the source cannot provide one, speedMps is
 * null and the UI shows it.
 */

export interface SpeedEstimate {
  speedMps: number | null;
  source: 'gnss' | 'ml' | 'sensor';
  /** 0..1 confidence in the estimate. */
  confidence: number;
}

export interface SpeedEstimator {
  readonly id: string;
  estimateSpeed(): SpeedEstimate;
}

export class GnssSpeedEstimator implements SpeedEstimator {
  readonly id = 'gnss';

  constructor(private readonly positionProvider: PositionProvider) {}

  estimateSpeed(): SpeedEstimate {
    const position = this.positionProvider.getCurrentPosition();
    if (!position) {
      return { speedMps: null, source: 'gnss', confidence: 0 };
    }
    if (position.speed === null) {
      return { speedMps: null, source: 'gnss', confidence: 0 };
    }
    const confident = position.status === 'available';
    return {
      speedMps: Math.max(0, position.speed),
      source: 'gnss',
      confidence: confident ? 1 : 0.5,
    };
  }
}

/**
 * CONTRACT ONLY — the ML speed model will implement this when the research
 * artifact is integrated. It never returns a value today.
 */
export class MLSpeedEstimator implements SpeedEstimator {
  readonly id = 'ml';

  estimateSpeed(): SpeedEstimate {
    return { speedMps: null, source: 'ml', confidence: 0 };
  }
}

/**
 * CONTRACT ONLY — sensor-based dead-reckoning speed estimation is a future
 * addition. Never returns a value today.
 */
export class SensorSpeedEstimator implements SpeedEstimator {
  readonly id = 'sensor';

  estimateSpeed(): SpeedEstimate {
    return { speedMps: null, source: 'sensor', confidence: 0 };
  }
}