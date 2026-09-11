import type {
  GeoPosition,
  PermissionState,
  PositionChangeListener,
  PositionProvider,
  PositioningStatus,
} from '@/types/position';

/**
 * Inertial Dead Reckoning provider — CONTRACT ONLY.
 *
 * This is the integration point for the research IDR/EKF module (Shatakshi's
 * work). Until that system is implemented and validated, this provider is
 * present so the architecture has a stable seam, and it deliberately:
 *
 *  - never returns a fabricated position
 *  - always reports `lost` (i.e. "no valid fix")
 *  - does nothing on start/stop
 *
 * The UI must never claim IDR is active. When the real implementation lands,
 * it will subscribe to the accelerometer/gyroscope streams (services/sensors)
 * and be wired into HybridPositionProvider as a fallback for GPS outages.
 */
export class IdrPositionProvider implements PositionProvider {
  readonly providerId = 'idr';
  readonly source = 'idr' as const;

  getPermissionState(): PermissionState {
    return 'unavailable';
  }

  getStatus(): PositioningStatus {
    return 'lost';
  }

  getCurrentPosition(): GeoPosition | null {
    return null;
  }

  subscribe(_listener: PositionChangeListener): () => void {
    return () => {};
  }

  requestPermission(): Promise<PermissionState> {
    return Promise.resolve('unavailable');
  }

  start(): Promise<void> {
    return Promise.resolve();
  }

  stop(): void {
    // no-op
  }
}