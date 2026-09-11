import type { PositioningStatus, PositionProvider } from '@/types/position';

const FRIENDLY_STATUS: Record<PositioningStatus, string> = {
  'gnss-connected': 'Location is accurate',
  'gnss-degraded': 'Signal is weak — accuracy reduced',
  'gnss-lost': 'GPS signal lost — navigation continues with intelligent positioning',
  recovering: 'Recovering signal',
  unknown: 'Positioning unavailable',
};

/** User-friendly status copy. No telemetry values ever appear here. */
export function friendlyStatus(status: PositioningStatus): string {
  return FRIENDLY_STATUS[status];
}

/**
 * Demo provider for previewing UI states only.
 *
 * It deliberately never produces coordinates, speed, or confidence values —
 * it only changes status text so the interface can be exercised end-to-end.
 */
export class StaticPositionProvider implements PositionProvider {
  readonly providerId = 'static-demo';
  private readonly listeners = new Set<(status: PositioningStatus) => void>();
  private current: PositioningStatus = 'gnss-connected';

  get status(): PositioningStatus {
    return this.current;
  }

  subscribe(listener: (status: PositioningStatus) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  setStatus(status: PositioningStatus): void {
    this.current = status;
    for (const listener of this.listeners) {
      listener(this.current);
    }
  }

  start(): void {
    // No-op for the demo provider.
  }

  stop(): void {
    // No-op for the demo provider.
  }
}