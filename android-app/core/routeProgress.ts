import { haversineDistanceMeters, nearestPointOnPolyline, polylineLengthMeters } from '@/core/geo';
import type { Coordinate, Maneuver, Route } from '@/types/routing';
import type { RouteProgressSnapshot } from '@/types/navigation';

/**
 * Route progress engine. Pure; injectable so the navigation math can be
 * unit-tested against synthetic routes.
 *
 * "Traveled" distance is measured along the route geometry (sum of haversine
 * legs — never a straight line between fixes).
 */

export interface RouteProgressInput {
  route: Route;
  point: Coordinate;
  /** Perpendicular deviation (meters) past which the user is off-route. */
  offRouteThresholdMeters: number;
  /** Radius (meters) around the destination that counts as arrived. */
  arrivalThresholdMeters: number;
  previouslyOffRoute?: boolean;
}

/**
 * Off-route detection with hysteresis: once off-route, we only return to
 * on-route when the deviation drops below 60% of the threshold.
 */
export function computeOffRoute(
  deviationMeters: number,
  thresholdMeters: number,
  previouslyOffRoute = false,
): boolean {
  if (thresholdMeters <= 0) return false;
  return previouslyOffRoute
    ? deviationMeters > thresholdMeters * 0.6
    : deviationMeters > thresholdMeters;
}

/** Distance along `route.geometry` from the origin to a given coordinate. */
function distanceAlongGeometryToCoordinate(route: Route, target: Coordinate): number {
  const coords = route.geometry;
  let accumulated = 0;
  for (let i = 0; i < coords.length; i++) {
    if (i > 0) accumulated += haversineDistanceMeters(coords[i - 1], coords[i]);
    if (Math.abs(coords[i].latitude - target.latitude) < 1e-9 &&
        Math.abs(coords[i].longitude - target.longitude) < 1e-9) {
      return accumulated;
    }
  }
  // Fallback: coordinate not found as a vertex — distance to the end plus the
  // final hop up to the target.
  if (coords.length === 0) return 0;
  return accumulated + haversineDistanceMeters(coords[coords.length - 1], target);
}

/**
 * Cumulative route distance at the start of each maneuver leg, precomputed
 * per route.
 */
export function maneuverStartDistances(route: Route): number[] {
  return route.maneuvers.map((m) =>
    m.coordinates.length === 0 ? 0 : distanceAlongGeometryToCoordinate(route, m.coordinates[0]),
  );
}

export interface NextManeuverInfo {
  currentManeuverIndex: number;
  nextManeuver: Maneuver | null;
  distanceToNextManeuverMeters: number;
  remainingManeuvers: Maneuver[];
}

/** Pick the next maneuver instruction given how far the user has traveled. */
export function findNextManeuver(
  route: Route,
  traveledDistanceMeters: number,
  maneuverStarts: number[],
): NextManeuverInfo {
  const maneuvers = route.maneuvers;
  if (maneuvers.length === 0) {
    return {
      currentManeuverIndex: 0,
      nextManeuver: null,
      distanceToNextManeuverMeters: 0,
      remainingManeuvers: [],
    };
  }

  let current = 0;
  for (let i = 0; i < maneuverStarts.length; i++) {
    if (maneuverStarts[i] <= traveledDistanceMeters + 1e-6) {
      current = i;
    } else {
      break;
    }
  }

  const nextIndex = Math.min(current + 1, maneuvers.length - 1);
  const nextManeuver = nextIndex !== current ? maneuvers[nextIndex] : null;

  return {
    currentManeuverIndex: current,
    nextManeuver,
    distanceToNextManeuverMeters:
      nextManeuver && maneuverStarts[nextIndex] !== undefined
        ? Math.max(0, maneuverStarts[nextIndex] - traveledDistanceMeters)
        : 0,
    remainingManeuvers: nextManeuver ? maneuvers.slice(nextIndex) : [],
  };
}

/** Compute a full progress snapshot from a single GPS fix. */
export function computeRouteProgress(
  input: RouteProgressInput,
): RouteProgressSnapshot | null {
  const { route, point } = input;
  if (route.geometry.length === 0) return null;

  const nearest = nearestPointOnPolyline(point, route.geometry);
  if (!nearest) return null;

  const totalLength =
    route.distanceMeters > 0 ? route.distanceMeters : polylineLengthMeters(route.geometry);
  const traveled = Math.min(nearest.distanceAlongMeters, totalLength);
  const remaining = Math.max(0, totalLength - traveled);
  const progress = totalLength <= 0 ? 0 : Math.min(1, Math.max(0, traveled / totalLength));

  const maneuverStarts = maneuverStartDistances(route);
  const instruction = findNextManeuver(route, traveled, maneuverStarts);

  const arrived = remaining <= input.arrivalThresholdMeters;
  const deviationMeters = nearest.distanceMeters;
  const offRoute = computeOffRoute(
    deviationMeters,
    input.offRouteThresholdMeters,
    input.previouslyOffRoute,
  );

  return {
    traveledDistanceMeters: traveled,
    remainingDistanceMeters: remaining,
    remainingDurationSeconds:
      remaining <= 0 ? 0 : (remaining / totalLength) * route.durationSeconds,
    progress,
    currentManeuverIndex: instruction.currentManeuverIndex,
    nextManeuver: instruction.nextManeuver,
    distanceToNextManeuverMeters: instruction.distanceToNextManeuverMeters,
    remainingManeuvers: instruction.remainingManeuvers,
    arrived,
    deviationMeters,
    offRoute,
  };
}