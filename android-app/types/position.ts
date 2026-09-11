/**
 * Provisional positioning contract.
 *
 * Real GNSS and IDR providers (GNSSPositionProvider / IDRPositionProvider)
 * will implement this interface during a later engineering phase. The UI only
 * depends on the status string — never on fabricated coordinates.
 */

export type PositioningStatus =
  | 'gnss-connected'
  | 'gnss-degraded'
  | 'gnss-lost'
  | 'recovering'
  | 'unknown';

export interface PositionProvider {
  readonly providerId: string;
  readonly status: PositioningStatus;
  /** Subscribe to status changes. Returns an unsubscribe function. */
  subscribe(listener: (status: PositioningStatus) => void): () => void;
  start(): void;
  stop(): void;
}