import type { Coordinate, Maneuver, Route, TravelMode } from '@/types/routing';
import type { GeoPosition, PositioningStatus, PositionSource } from '@/types/position';

/**
 * High-level navigation session state machine phase.
 *
 * - idle: no active session
 * - searching: a destination was picked, route computation pending
 * - calculating: routing request in flight
 * - routeReady: a route is displayed but navigation has not started
 * - starting: navigation started; waiting for the first usable GPS fix
 * - navigating: turn-by-turn guidance active
 * - degraded: navigating with reduced GPS accuracy (truthful; no fake IDR)
 * - lost:   GPS fix lost — guidance pauses until a signal returns
 * - recovering: GPS updates resumed after a loss; settling for a few seconds
 * - rerouting: off-route detection triggered; new route being computed
 * - arrived: destination reached
 * - error: something failed (routing, permissions, etc.)
 */
export type NavPhase =
  | 'idle'
  | 'searching'
  | 'calculating'
  | 'routeReady'
  | 'starting'
  | 'navigating'
  | 'degraded'
  | 'lost'
  | 'recovering'
  | 'rerouting'
  | 'arrived'
  | 'error';

export interface RouteProgressSnapshot {
  /** Meters traveled along the route from the origin. */
  traveledDistanceMeters: number;
  /** Meters still to go from the snapped position to the destination. */
  remainingDistanceMeters: number;
  /** Estimated seconds remaining (from route duration scaled by progress). */
  remainingDurationSeconds: number;
  /** 0 → 1 fraction of the route covered. */
  progress: number;
  /** Index of the maneuver leg that starts just after the current position. */
  currentManeuverIndex: number;
  /** The next maneuver the user will perform, or null when arriving. */
  nextManeuver: Maneuver | null;
  /** Distance in meters from the snapped position to the next maneuver. */
  distanceToNextManeuverMeters: number;
  remainingManeuvers: Maneuver[];
  /** True when the destination is within the arrival threshold. */
  arrived: boolean;
  /** Perpendicular distance in meters from the route line. */
  deviationMeters: number;
  /** True when deviation has exceeded the off-route threshold. */
  offRoute: boolean;
}

export interface NavigationSnapshot {
  phase: NavPhase;
  route: Route | null;
  destination: Coordinate | null;
  travelMode: TravelMode | null;
  position: GeoPosition | null;
  positioningStatus: PositioningStatus;
  positionSource: PositionSource;
  progress: RouteProgressSnapshot | null;
  /** Estimated arrival as epoch milliseconds, or null when not navigating. */
  etaMillis: number | null;
  /** Best estimate of current speed in m/s, or null. */
  speedMps: number | null;
  /** Best estimate of heading in degrees, or null. */
  headingDeg: number | null;
  /** True while a reroute request is in flight. */
  rerouting: boolean;
  /** User-safe error message, or null. */
  error: string | null;
}