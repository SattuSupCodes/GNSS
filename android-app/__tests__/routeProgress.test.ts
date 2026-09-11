import { computeOffRoute, findNextManeuver, maneuverStartDistances, computeRouteProgress } from '@/core/routeProgress';
import type { Route } from '@/types/routing';

function makeRoute(): Route {
  return {
    geometry: [
      { latitude: 25.0, longitude: 55.0 },
      { latitude: 25.05, longitude: 55.05 },
      { latitude: 25.1, longitude: 55.1 },
    ],
    distanceMeters: 1200,
    durationSeconds: 300,
    maneuvers: [
      { action: 'depart', instruction: 'Leave', approachDistanceMeters: 0, approachDurationSeconds: 0, coordinates: [{ latitude: 25.0, longitude: 55.0 }] },
      { action: 'turn-right', instruction: 'Turn right', approachDistanceMeters: 500, approachDurationSeconds: 120, coordinates: [{ latitude: 25.05, longitude: 55.05 }] },
      { action: 'arrive', instruction: 'Arrive', approachDistanceMeters: 1200, approachDurationSeconds: 300, coordinates: [{ latitude: 25.1, longitude: 55.1 }] },
    ],
    bounds: { southwest: { latitude: 25.0, longitude: 55.0 }, northeast: { latitude: 25.1, longitude: 55.1 } },
  };
}

describe('maneuverStartDistances', () => {
  it('returns cumulative distances along the geometry, starting at 0', () => {
    const starts = maneuverStartDistances(makeRoute());
    expect(starts).toHaveLength(3);
    expect(starts[0]).toBeCloseTo(0, 5);
    expect(starts[1]).toBeGreaterThan(starts[0]);
    expect(starts[2]).toBeGreaterThan(starts[1]);
  });

  it('returns [0,0,...] when maneuvers have no coordinates', () => {
    const route = makeRoute();
    route.maneuvers = route.maneuvers.map((m) => ({ ...m, coordinates: [] }));
    expect(maneuverStartDistances(route)).toEqual([0, 0, 0]);
  });
});

describe('findNextManeuver', () => {
  it('returns the first maneuver leg as next at the origin', () => {
    const route = makeRoute();
    const starts = maneuverStartDistances(route);
    const result = findNextManeuver(route, 0, starts);
    expect(result.currentManeuverIndex).toBe(0);
    expect(result.nextManeuver?.action).toBe('turn-right');
    expect(result.distanceToNextManeuverMeters).toBeCloseTo(starts[1], 3);
    expect(result.remainingManeuvers).toHaveLength(2);
  });

  it('advances when traveled past a maneuver start', () => {
    const route = makeRoute();
    const starts = maneuverStartDistances(route);
    const result = findNextManeuver(route, starts[1] + 1, starts);
    expect(result.currentManeuverIndex).toBe(1);
    expect(result.nextManeuver?.action).toBe('arrive');
  });

  it('returns null maneuvers for empty route maneuvers', () => {
    const route = makeRoute();
    route.maneuvers = [];
    const result = findNextManeuver(route, 0, [0]);
    expect(result.nextManeuver).toBeNull();
    expect(result.remainingManeuvers).toEqual([]);
  });
});

describe('computeOffRoute', () => {
  it('returns false when within threshold', () => {
    expect(computeOffRoute(0, 30)).toBe(false);
    expect(computeOffRoute(25, 30)).toBe(false);
  });

  it('returns true past the threshold', () => {
    expect(computeOffRoute(31, 30)).toBe(true);
    expect(computeOffRoute(60, 30)).toBe(true);
  });

  it('applies hysteresis once already off-route', () => {
    expect(computeOffRoute(25, 30, true)).toBe(true);
    expect(computeOffRoute(10, 30, true)).toBe(false);
  });

  it('never trips with a non-positive threshold', () => {
    expect(computeOffRoute(1000, 0)).toBe(false);
  });
});

describe('computeRouteProgress', () => {
  it('returns a valid snapshot at the origin', () => {
    const progress = computeRouteProgress({
      route: makeRoute(),
      point: { latitude: 25.0, longitude: 55.0 },
      offRouteThresholdMeters: 30,
      arrivalThresholdMeters: 20,
    });
    expect(progress).not.toBeNull();
    expect(progress!.traveledDistanceMeters).toBeCloseTo(0, 3);
    expect(progress!.remainingDistanceMeters).toBeCloseTo(1200, 0);
    expect(progress!.arrived).toBe(false);
    expect(progress!.offRoute).toBe(false);
    expect(progress!.currentManeuverIndex).toBe(0);
  });

  it('flags arrival near the destination', () => {
    const route = makeRoute();
    const progress = computeRouteProgress({
      route,
      point: { latitude: 25.1, longitude: 55.1 },
      offRouteThresholdMeters: 30,
      arrivalThresholdMeters: 20,
    });
    expect(progress).not.toBeNull();
    expect(progress!.arrived).toBe(true);
    expect(progress!.remainingDistanceMeters).toBeLessThanOrEqual(20);
  });

  it('returns null for a route with no geometry', () => {
    const route = makeRoute();
    route.geometry = [];
    expect(
      computeRouteProgress({
        route,
        point: { latitude: 25.0, longitude: 55.0 },
        offRouteThresholdMeters: 30,
        arrivalThresholdMeters: 20,
      }),
    ).toBeNull();
  });
});