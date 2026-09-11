import { estimateRemainingSeconds, estimateArrivalMillis, estimateEtaMillis, formatEtaTime, formatRemainingDuration } from '@/core/eta';
import type { Route } from '@/types/routing';
import type { RouteProgressSnapshot } from '@/types/navigation';

const route: Route = {
  geometry: [{ latitude: 25.0, longitude: 55.0 }, { latitude: 25.1, longitude: 55.1 }],
  maneuvers: [],
  distanceMeters: 2000,
  durationSeconds: 600,
  bounds: null,
};

function progress(overrides: Partial<RouteProgressSnapshot>): RouteProgressSnapshot {
  return {
    traveledDistanceMeters: 1000,
    remainingDistanceMeters: 1000,
    remainingDurationSeconds: 300,
    progress: 0.5,
    currentManeuverIndex: 0,
    nextManeuver: null,
    distanceToNextManeuverMeters: 0,
    remainingManeuvers: [],
    arrived: false,
    deviationMeters: 0,
    offRoute: false,
    ...overrides,
  };
}

describe('estimateRemainingSeconds', () => {
  it('uses live speed when moving', () => {
    const result = estimateRemainingSeconds({ route, progress: progress({}), currentSpeedMps: 10 });
    expect(result).toBeGreaterThan(0);
    expect(result).toBeLessThan(300);
  });

  it('uses route estimate when speed is too low', () => {
    const result = estimateRemainingSeconds({ route, progress: progress({}), currentSpeedMps: 0 });
    expect(result).toBeCloseTo(300, 0);
  });

  it('returns 0 when arrived or no distance remaining', () => {
    const result = estimateRemainingSeconds({ route, progress: progress({ arrived: true, remainingDistanceMeters: 0 }), currentSpeedMps: 5 });
    expect(result).toBe(0);
  });
});

describe('estimateArrivalMillis', () => {
  it('returns a future timestamp', () => {
    const now = Date.now();
    const arrival = estimateArrivalMillis(120, now);
    expect(arrival).toBeCloseTo(now + 120_000, -2);
  });
});

describe('estimateEtaMillis', () => {
  it('returns null when nothing remains', () => {
    expect(estimateEtaMillis({ route, progress: progress({ arrived: true, remainingDistanceMeters: 0 }), currentSpeedMps: 5, now: Date.now() })).toBeNull();
  });

  it('returns a future timestamp when inputs are valid', () => {
    const result = estimateEtaMillis({ route, progress: progress({}), currentSpeedMps: 10, now: Date.now() });
    expect(result).toBeGreaterThan(Date.now());
  });
});

describe('formatEtaTime', () => {
  it('returns placeholder for null', () => {
    expect(formatEtaTime(null)).toBe('--');
  });

  it('formats valid timestamp', () => {
    const result = formatEtaTime(Date.now() + 60 * 60 * 1000);
    expect(result).toMatch(/^\d{1,2}:\d{2} (AM|PM)$/);
  });
});

describe('formatRemainingDuration', () => {
  it('returns placeholder for null', () => {
    expect(formatRemainingDuration(null)).toBe('--');
  });

  it('formats seconds', () => {
    expect(formatRemainingDuration(45)).toBe('45s');
  });

  it('formats minutes and seconds', () => {
    expect(formatRemainingDuration(122)).toBe('2m 2s');
  });

  it('formats hours and minutes', () => {
    expect(formatRemainingDuration(3660)).toBe('1h 1m');
  });
});