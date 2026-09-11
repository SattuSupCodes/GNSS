import { haversineDistanceMeters, bearingDegrees, normalizeDegrees, headingDeltaDegrees, smoothHeadingDegrees, polylineLengthMeters, nearestPointOnPolyline, deviationFromPolylineMeters } from '@/core/geo';

describe('haversineDistanceMeters', () => {
  it('returns 0 for identical points', () => {
    expect(haversineDistanceMeters({ latitude: 25.0, longitude: 55.0 }, { latitude: 25.0, longitude: 55.0 })).toBe(0);
  });

  it('returns a positive number for different points', () => {
    const d = haversineDistanceMeters({ latitude: 25.0, longitude: 55.0 }, { latitude: 25.1, longitude: 55.1 });
    expect(d).toBeGreaterThan(0);
  });

  it('is symmetric', () => {
    const a = { latitude: 25.0, longitude: 55.0 };
    const b = { latitude: 26.0, longitude: 56.0 };
    expect(haversineDistanceMeters(a, b)).toBeCloseTo(haversineDistanceMeters(b, a), 5);
  });
});

describe('bearingDegrees', () => {
  it('returns ~0 for due north', () => {
    const bearing = bearingDegrees({ latitude: 25.0, longitude: 55.0 }, { latitude: 26.0, longitude: 55.0 });
    expect(bearing).toBeCloseTo(0, 0);
  });

  it('returns ~90 for due east', () => {
    const bearing = bearingDegrees({ latitude: 25.0, longitude: 55.0 }, { latitude: 25.0, longitude: 56.0 });
    expect(bearing).toBeCloseTo(90, 0);
  });
});

describe('normalizeDegrees', () => {
  it('normalizes angles to [0, 360)', () => {
    expect(normalizeDegrees(-90)).toBeCloseTo(270);
    expect(normalizeDegrees(400)).toBeCloseTo(40);
    expect(normalizeDegrees(360)).toBeCloseTo(0);
  });
});

describe('headingDeltaDegrees', () => {
  it('returns 0 for same heading', () => {
    expect(headingDeltaDegrees(10, 10)).toBeCloseTo(0);
  });

  it('returns signed deltas in [-180, 180]', () => {
    expect(headingDeltaDegrees(10, 350)).toBeCloseTo(-20);
    expect(headingDeltaDegrees(350, 10)).toBeCloseTo(20);
  });
});

describe('smoothHeadingDegrees', () => {
  it('returns normalized raw when previous is null', () => {
    expect(smoothHeadingDegrees(null, 45, 0.5)).toBeCloseTo(45);
  });

  it('blends toward the raw heading', () => {
    const result = smoothHeadingDegrees(40, 50, 0.5);
    expect(result).toBeGreaterThanOrEqual(40);
    expect(result).toBeLessThanOrEqual(50);
  });

  it('handles wraparound smoothly', () => {
    const result = smoothHeadingDegrees(355, 5, 0.5);
    expect(Math.min(result, 360 - result)).toBeLessThan(10);
  });
});

describe('polylineLengthMeters', () => {
  it('returns 0 for empty/single point', () => {
    expect(polylineLengthMeters([])).toBe(0);
    expect(polylineLengthMeters([{ latitude: 25, longitude: 55 }])).toBe(0);
  });

  it('sums segment distances', () => {
    const length = polylineLengthMeters([
      { latitude: 25.0, longitude: 55.0 },
      { latitude: 25.1, longitude: 55.0 },
      { latitude: 25.1, longitude: 55.1 },
    ]);
    expect(length).toBeGreaterThan(0);
  });
});

describe('nearestPointOnPolyline', () => {
  it('finds a point on a straight segment', () => {
    const a = { latitude: 25.0, longitude: 55.0 };
    const b = { latitude: 25.0, longitude: 55.1 };
    const point = { latitude: 25.001, longitude: 55.05 };
    const nearest = nearestPointOnPolyline(point, [a, b]);
    expect(nearest).not.toBeNull();
    expect(nearest!.point.latitude).toBeCloseTo(25.0, 4);
    expect(nearest!.point.longitude).toBeCloseTo(55.05, 4);
  });
});

describe('deviationFromPolylineMeters', () => {
  it('returns 0 when on the line', () => {
    const line = [
      { latitude: 25.0, longitude: 55.0 },
      { latitude: 25.0, longitude: 55.1 },
    ];
    expect(deviationFromPolylineMeters({ latitude: 25.0, longitude: 55.05 }, line)).toBeCloseTo(0, 5);
  });

  it('returns positive value when off the line', () => {
    const line = [
      { latitude: 25.0, longitude: 55.0 },
      { latitude: 25.0, longitude: 55.1 },
    ];
    const dev = deviationFromPolylineMeters({ latitude: 25.01, longitude: 55.05 }, line);
    expect(dev).toBeGreaterThan(0);
  });
});