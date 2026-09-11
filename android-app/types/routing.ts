/**
 * Routing domain model.
 */

import type { IconName } from '@/components/Icon';

export type TravelMode = 'car' | 'foot' | 'bike';

export interface TravelModeOption {
  id: TravelMode;
  label: string;
  icon: IconName;
  /** GraphHopper vehicle/profile parameter value. */
  vehicle: string;
}

export const TRAVEL_MODE_OPTIONS: TravelModeOption[] = [
  { id: 'car', label: 'Drive', icon: 'car', vehicle: 'car' },
  { id: 'foot', label: 'Walk', icon: 'walk', vehicle: 'foot' },
  { id: 'bike', label: 'Cycle', icon: 'bike', vehicle: 'bike' },
];

export function vehicleForMode(mode: TravelMode): string {
  return TRAVEL_MODE_OPTIONS.find((o) => o.id === mode)?.vehicle ?? 'car';
}

export type ManeuverAction =
  | 'depart'
  | 'arrive'
  | 'turn-left'
  | 'turn-right'
  | 'turn-slight-left'
  | 'turn-slight-right'
  | 'turn-sharp-left'
  | 'turn-sharp-right'
  | 'straight'
  | 'uturn'
  | 'roundabout-right'
  | 'keep-left'
  | 'keep-right';

export interface Coordinate {
  latitude: number;
  longitude: number;
}

export interface Maneuver {
  action: ManeuverAction;
  /** Human-readable instruction, e.g. "Turn right onto Main Street". */
  instruction: string;
  /** Distance in meters from the previous maneuver to this one. */
  approachDistanceMeters: number;
  /** Estimated approach duration in seconds. */
  approachDurationSeconds: number;
  /** Coordinates making up this maneuver's leg. */
  coordinates: Coordinate[];
  /** Exit number (roundabouts only), if reported by the routing engine. */
  exitNumber?: number;
}

export interface Bounds {
  southwest: Coordinate;
  northeast: Coordinate;
}

export interface Route {
  /** Full geometry, ordered origin → destination. */
  geometry: Coordinate[];
  distanceMeters: number;
  durationSeconds: number;
  maneuvers: Maneuver[];
  bounds: Bounds | null;
}

export interface RouteOptions {
  travelMode: TravelMode;
  /** Number of alternative routes requested (0 = single route). */
  alternatives?: number;
  locale?: string;
  /** Prefer route distance over time. */
  timePreference?: boolean;
}

export interface RouteRequest {
  origin: Coordinate;
  destination: Coordinate;
  options: RouteOptions;
}

export interface RouteResult {
  routes: Route[];
  request: RouteRequest;
  /** Raw engine response kept for diagnostics when available. */
  provider: string;
}

/** Thrown by routing services; message is always user-safe. */
export class RoutingError extends Error {
  constructor(
    message: string,
    readonly code: 'no_key' | 'network' | 'server' | 'invalid' | 'no_position',
  ) {
    super(message);
    this.name = 'RoutingError';
  }
}