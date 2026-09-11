import { navigationMachine, EMPTY_MACHINE_STATE, type MachineState } from '@/core/navigationMachine';
import type { Route } from '@/types/routing';

const destination = { latitude: 25.1, longitude: 55.1 };
const route: Route = {
  geometry: [{ latitude: 25.0, longitude: 55.0 }, { latitude: 25.1, longitude: 55.1 }],
  maneuvers: [],
  distanceMeters: 1000,
  durationSeconds: 200,
  bounds: null,
};

describe('navigationMachine', () => {
  it('starts idle', () => {
    expect(EMPTY_MACHINE_STATE.phase).toBe('idle');
  });

  it('select destination enters searching', () => {
    const s = navigationMachine(EMPTY_MACHINE_STATE, { type: 'SELECT_DESTINATION', destination, mode: 'car' });
    expect(s.phase).toBe('searching');
    expect(s.destination).toEqual(destination);
  });

  it('calculate route enters calculating', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'searching', destination },
      { type: 'CALCULATE_ROUTE' },
    );
    expect(s.phase).toBe('calculating');
  });

  it('route success enters routeReady', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'calculating', destination, travelMode: 'car' },
      { type: 'ROUTE_SUCCESS', route },
    );
    expect(s.phase).toBe('routeReady');
    expect(s.route).toEqual(route);
  });

  it('route failure enters error', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'calculating', destination },
      { type: 'ROUTE_FAILURE', message: 'Network error' },
    );
    expect(s.phase).toBe('error');
    expect(s.error).toBe('Network error');
  });

  it('start navigation enters starting', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'routeReady', route, destination, travelMode: 'car' },
      { type: 'START_NAVIGATION' },
    );
    expect(s.phase).toBe('starting');
  });

  it('POSITION_UPDATE with available moves starting to navigating', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'starting', route, destination },
      { type: 'POSITION_UPDATE', status: 'available' },
    );
    expect(s.phase).toBe('navigating');
  });

  it('STATUS_CHANGE to lost while navigating enters lost', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'navigating', route, destination },
      { type: 'STATUS_CHANGE', status: 'lost' },
    );
    expect(s.phase).toBe('lost');
  });

  it('OFF_ROUTE_DETECTED while navigating enters rerouting', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'navigating', route, destination },
      { type: 'OFF_ROUTE_DETECTED' },
    );
    expect(s.phase).toBe('rerouting');
    expect(s.rerouting).toBe(true);
  });

  it('REROUTE_SUCCESS restores navigating', () => {
    const rerouted: Route = { ...route };
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'rerouting', route, destination },
      { type: 'REROUTE_SUCCESS', route: rerouted },
    );
    expect(s.phase).toBe('navigating');
    expect(s.route).toEqual(rerouted);
    expect(s.rerouting).toBe(false);
  });

  it('ARRIVED enters arrived', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'navigating', route, destination },
      { type: 'ARRIVED' },
    );
    expect(s.phase).toBe('arrived');
  });

  it('CANCEL resets to idle', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'navigating', route, destination },
      { type: 'CANCEL' },
    );
    expect(s).toEqual(EMPTY_MACHINE_STATE);
  });

  it('RESET_ERROR clears the error', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'error', error: 'boom', destination },
      { type: 'RESET_ERROR' },
    );
    expect(s.error).toBeNull();
    expect(s.phase).toBe('error');
  });

  it('STATUS_CHANGE is ignored outside navigating phases', () => {
    const s = navigationMachine(
      { ...EMPTY_MACHINE_STATE, phase: 'idle' },
      { type: 'STATUS_CHANGE', status: 'lost' },
    );
    expect(s.phase).toBe('idle');
  });
});