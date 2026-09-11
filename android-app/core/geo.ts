import type { Coordinate } from '@/types/routing';

/**
 * Pure geodetic helpers. Everything here is unit-tested and dependency-free
 * so the navigation math can be verified independently of any native code.
 *
 * Distances use the haversine formula on the WGS84 sphere — never a naive
 * Cartesian difference between raw latitude/longitude.
 */

export const EARTH_RADIUS_METERS = 6_371_008.8;

export const DEG_TO_RAD = Math.PI / 180;
export const RAD_TO_DEG = 180 / Math.PI;

export function toRadians(degrees: number): number {
  return degrees * DEG_TO_RAD;
}

export function toDegrees(radians: number): number {
  return radians * RAD_TO_DEG;
}

/** Great-circle distance between two coordinates in meters. */
export function haversineDistanceMeters(a: Coordinate, b: Coordinate): number {
  const lat1 = toRadians(a.latitude);
  const lat2 = toRadians(b.latitude);
  const dLat = lat2 - lat1;
  const dLon = toRadians(b.longitude - a.longitude);

  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Initial bearing from `a` toward `b`, in degrees clockwise from north. */
export function bearingDegrees(a: Coordinate, b: Coordinate): number {
  const lat1 = toRadians(a.latitude);
  const lat2 = toRadians(b.latitude);
  const dLon = toRadians(b.longitude - a.longitude);

  const y = Math.sin(dLon) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  return normalizeDegrees(toDegrees(Math.atan2(y, x)));
}

/** Wrap any angle (degrees) into [0, 360). */
export function normalizeDegrees(degrees: number): number {
  const wrapped = degrees % 360;
  return wrapped < 0 ? wrapped + 360 : wrapped;
}

/** Signed difference (deg) from `from` to `to`, normalized to [-180, 180]. */
export function headingDeltaDegrees(from: number, to: number): number {
  let delta = to - from;
  while (delta > 180) delta -= 360;
  while (delta < -180) delta += 360;
  return delta;
}

/**
 * Wraparound-correct exponential moving average for compass headings.
 * Returns the previous value when `raw` is invalid.
 */
export function smoothHeadingDegrees(
  previous: number | null,
  raw: number,
  alpha: number,
): number {
  if (previous === null || !Number.isFinite(raw)) {
    return normalizeDegrees(raw);
  }
  const prev = normalizeDegrees(previous);
  const adj = prev + headingDeltaDegrees(prev, raw);
  return normalizeDegrees(prev * (1 - alpha) + adj * alpha);
}

/**
 * Total length in meters of a polyline (sum of haversine segment lengths).
 */
export function polylineLengthMeters(coordinates: Coordinate[]): number {
  let total = 0;
  for (let i = 0; i < coordinates.length - 1; i++) {
    total += haversineDistanceMeters(coordinates[i], coordinates[i + 1]);
  }
  return total;
}

/** Bounding box of a coordinate list, or null when empty. */
export function coordinatesToBounds(
  coordinates: Coordinate[],
): { southwest: Coordinate; northeast: Coordinate } | null {
  if (coordinates.length === 0) return null;
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;
  for (const c of coordinates) {
    if (c.latitude < minLat) minLat = c.latitude;
    if (c.latitude > maxLat) maxLat = c.latitude;
    if (c.longitude < minLon) minLon = c.longitude;
    if (c.longitude > maxLon) maxLon = c.longitude;
  }
  return {
    southwest: { latitude: minLat, longitude: minLon },
    northeast: { latitude: maxLat, longitude: maxLon },
  };
}

export function isWithinRadius(p: Coordinate, center: Coordinate, meters: number): boolean {
  return haversineDistanceMeters(p, center) <= meters;
}

interface SegmentProjection {
  /** Closest point on the segment. */
  point: Coordinate;
  /** Fraction [0,1] along the segment. */
  t: number;
  /** Distance along segment to the projection (meters). */
  alongMeters: number;
}

/**
 * Closest point on segment ab with fast local planar projection (fine at
 * street scale) then refined with the exact haversine distance.
 */
export function projectToSegment(
  point: Coordinate,
  a: Coordinate,
  b: Coordinate,
): SegmentProjection {
  const latRad = toRadians(a.latitude);
  const metersPerDegLat = 110_540;
  const metersPerDegLon = 111_320 * Math.cos(latRad);

  // Planar coordinates in meters.
  const ax = a.longitude * metersPerDegLon;
  const ay = a.latitude * metersPerDegLat;
  const bx = b.longitude * metersPerDegLon;
  const by = b.latitude * metersPerDegLat;
  const px = point.longitude * metersPerDegLon;
  const py = point.latitude * metersPerDegLat;

  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  const t = lenSq <= 0 ? 0 : Math.min(1, Math.max(0, ((px - ax) * dx + (py - ay) * dy) / lenSq));

  const projLon = (ax + t * dx) / metersPerDegLon;
  const projLat = (ay + t * dy) / metersPerDegLat;

  return {
    point: { latitude: projLat, longitude: projLon },
    t,
    alongMeters: lenSq <= 0 ? 0 : t * Math.sqrt(lenSq),
  };
}

export interface NearestOnPolyline {
  /** Index of the segment [i, i+1] that contains the nearest point. */
  segmentIndex: number;
  point: Coordinate;
  /** Exact great-circle distance from the input point to the polyline. */
  distanceMeters: number;
  /** Distance along the polyline from its start to the nearest point. */
  distanceAlongMeters: number;
}

/** Brute-force nearest point on a polyline. */
export function nearestPointOnPolyline(
  point: Coordinate,
  polyline: Coordinate[],
): NearestOnPolyline | null {
  if (polyline.length === 0) return null;
  if (polyline.length === 1) {
    return {
      segmentIndex: 0,
      point: polyline[0],
      distanceMeters: haversineDistanceMeters(point, polyline[0]),
      distanceAlongMeters: 0,
    };
  }

  let best: NearestOnPolyline | null = null;
  let accumulated = 0;
  for (let i = 0; i < polyline.length - 1; i++) {
    const a = polyline[i];
    const b = polyline[i + 1];
    const projection = projectToSegment(point, a, b);
    const distanceMeters = haversineDistanceMeters(point, projection.point);
    const distanceAlongMeters = accumulated + projection.alongMeters;
    if (!best || distanceMeters < best.distanceMeters) {
      best = {
        segmentIndex: i,
        point: projection.point,
        distanceMeters,
        distanceAlongMeters,
      };
    }
    accumulated += haversineDistanceMeters(a, b);
  }
  return best;
}

/** Distance in meters from a point to its nearest route point (perpendicular-ish). */
export function deviationFromPolylineMeters(
  point: Coordinate,
  polyline: Coordinate[],
): number {
  const nearest = nearestPointOnPolyline(point, polyline);
  return nearest?.distanceMeters ?? Infinity;
}

/** Coordinate a given distance (meters) along a polyline from its start. */
export function coordinateAtDistance(polyline: Coordinate[], distanceMeters: number): Coordinate {
  if (polyline.length === 0) return { latitude: 0, longitude: 0 };
  if (polyline.length === 1) return polyline[0];
  let remaining = Math.max(0, distanceMeters);
  for (let i = 0; i < polyline.length - 1; i++) {
    const a = polyline[i];
    const b = polyline[i + 1];
    const segLen = haversineDistanceMeters(a, b);
    if (remaining <= segLen || i === polyline.length - 2) {
      const t = segLen <= 0 ? 0 : remaining / segLen;
      return {
        latitude: a.latitude + (b.latitude - a.latitude) * t,
        longitude: a.longitude + (b.longitude - a.longitude) * t,
      };
    }
    remaining -= segLen;
  }
  return polyline[polyline.length - 1];
}