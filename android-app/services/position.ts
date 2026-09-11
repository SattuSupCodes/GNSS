import { GnssPositionProvider } from '@/services/position/gnssPositionProvider';
import { HybridPositionProvider } from '@/services/position/hybridPositionProvider';
import { IdrPositionProvider } from '@/services/position/idrPositionProvider';
import { DemoPositionProvider } from '@/services/position/demoPositionProvider';
import type { PositionProvider, PositioningStatus } from '@/types/position';
import type { Coordinate } from '@/types/routing';

/**
 * Positioning entry point.
 *
 * The default provider is GNSS wrapped in the hybrid seam (today only GNSS
 * produces fixes — see hybridPositionProvider.ts). IDR is present as a
 * contract-only provider and never claims a fix.
 *
 * Status copy is deliberately truthful: when there is no fix it says exactly
 * that. There is no fabricated "intelligent positioning" fallback.
 */

const FRIENDLY_STATUS: Record<PositioningStatus, string> = {
  available: 'Location is accurate',
  degraded: 'GPS signal is weak — accuracy reduced',
  lost: 'GPS signal lost — waiting for a stronger signal',
  recovering: 'Recovering GPS signal',
};

export function friendlyPositionText(status: PositioningStatus): string {
  return FRIENDLY_STATUS[status];
}

// Backwards-compatible alias kept for existing UI call sites.
export const friendlyStatus = friendlyPositionText;

/** The production provider graph: GNSS (now) → IDR (future contract). */
export function createDefaultPositionProvider(): PositionProvider {
  const gnss = new GnssPositionProvider();
  const idr = new IdrPositionProvider(); // contract only
  return new HybridPositionProvider([gnss, idr]);
}

/**
 * Demo provider for exercising the navigation UI without GPS. Explicitly a
 * simulation — creating one signals the developer's intent in the UI legend.
 */
export function createDemoPositionProvider(path: Coordinate[]): DemoPositionProvider {
  return new DemoPositionProvider(path);
}