import { classifyGnssHealth, transitionGnssStatus } from '@/core/gnssHealth';

const NOW = 1_000_000;

describe('classifyGnssHealth', () => {
  it('reports lost while never fixed', () => {
    expect(classifyGnssHealth({ lastFixMillis: null, accuracyMeters: 5, now: NOW })).toBe('lost');
  });

  it('reports available for a fresh, accurate fix', () => {
    expect(classifyGnssHealth({ lastFixMillis: NOW - 1_000, accuracyMeters: 5, now: NOW })).toBe('available');
  });

  it('reports degraded for poor accuracy', () => {
    expect(classifyGnssHealth({ lastFixMillis: NOW - 1_000, accuracyMeters: 100, now: NOW })).toBe('degraded');
  });

  it('reports degraded when accuracy is unknown', () => {
    expect(classifyGnssHealth({ lastFixMillis: NOW - 1_000, accuracyMeters: null, now: NOW })).toBe('degraded');
  });

  it('reports lost for a stale fix', () => {
    expect(classifyGnssHealth({ lastFixMillis: NOW - 20_000, accuracyMeters: 5, now: NOW })).toBe('lost');
  });
});

describe('transitionGnssStatus', () => {
  it('joins recovering on first fix after loss', () => {
    const transition = transitionGnssStatus('lost', 'available', NOW, null);
    expect(transition.status).toBe('recovering');
    expect(transition.recoveringUntil).toBe(NOW + 6_000);
  });

  it('stays recovering within the grace window', () => {
    const transition = transitionGnssStatus('recovering', 'available', NOW, NOW + 6_000);
    expect(transition.status).toBe('recovering');
  });

  it('returns available once the grace window elapses', () => {
    const transition = transitionGnssStatus('recovering', 'available', NOW, NOW - 1_000);
    expect(transition.status).toBe('available');
    expect(transition.recoveringUntil).toBeNull();
  });

  it('maps classified lost directly to lost', () => {
    const transition = transitionGnssStatus('available', 'lost', NOW, null);
    expect(transition.status).toBe('lost');
    expect(transition.recoveringUntil).toBeNull();
  });

  it('keeps an already-current status when healthy', () => {
    const transition = transitionGnssStatus('available', 'available', NOW, null);
    expect(transition.status).toBe('available');
  });
});