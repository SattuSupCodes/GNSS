/**
 * Positioning domain model.
 *
 * Every position fix the app works with is normalized into a GeoPosition.
 * Providers (GNSS today; IDR/hybrid as future contracts) implement
 * PositionProvider. The UI never fabricates coordinates: when there is no
 * valid fix the position is simply `null` and the status explains why.
 */

/** Health of the positioning source, not the accuracy of the map. */
export type PositioningStatus =
  | 'available'
  | 'degraded'
  | 'lost'
  | 'recovering';

/** Where a GeoPosition came from. `idr` and `hybrid` are future contracts. */
export type PositionSource = 'gnss' | 'idr' | 'hybrid' | 'unknown';

/** Normalized, unit-consistent position fix. */
export interface GeoPosition {
  latitude: number;
  longitude: number;
  /** Meters above WGS84 ellipsoid, or null when the source can't tell. */
  altitude: number | null;
  /** Horizontal accuracy radius in meters, or null. */
  accuracy: number | null;
  /** Speed in meters/second (course over ground), or null. */
  speed: number | null;
  /** Course over ground in degrees clockwise from true north, or null. */
  heading: number | null;
  /** Epoch milliseconds when the fix was captured. */
  timestamp: number;
  source: PositionSource;
  status: PositioningStatus;
}

export type PermissionState =
  | 'undetermined'
  | 'granted'
  | 'denied'
  | 'restricted'
  | 'unavailable';

export type PositionChangeListener = (position: GeoPosition | null) => void;

export interface PositionProvider {
  readonly providerId: string;
  readonly source: PositionSource;

  getCurrentPosition(): GeoPosition | null;
  getStatus(): PositioningStatus;
  getPermissionState(): PermissionState;

  requestPermission(): Promise<PermissionState>;
  /** Subscribe to position changes. Returns an unsubscribe function. */
  subscribe(listener: PositionChangeListener): () => void;

  start(): Promise<void>;
  stop(): void;
}