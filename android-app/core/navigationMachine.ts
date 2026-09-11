import type { Coordinate, Route, TravelMode } from '@/types/routing';
import type { NavPhase } from '@/types/navigation';
import type { PositioningStatus } from '@/types/position';

/**
 * Navigation state machine — a pure reducer over discrete events.
 *
 * Runtime data (position, progress, ETA, heading) lives in the orchestrator;
 * this reducer only owns the *phase* and session identity (route, destination,
 * travel mode, error). Keeping it pure makes every transition unit-testable.
 */

export type NavEvent =
  | { type: 'SELECT_DESTINATION'; destination: Coordinate; mode: TravelMode }
  | { type: 'CALCULATE_ROUTE' }
  | { type: 'ROUTE_SUCCESS'; route: Route }
  | { type: 'ROUTE_FAILURE'; message: string }
  | { type: 'START_NAVIGATION' }
  | { type: 'POSITION_UPDATE'; status: PositioningStatus }
  | { type: 'STATUS_CHANGE'; status: PositioningStatus }
  | { type: 'OFF_ROUTE_DETECTED' }
  | { type: 'REROUTE_SUCCESS'; route: Route }
  | { type: 'REROUTE_FAILURE'; message: string }
  | { type: 'ARRIVED' }
  | { type: 'CANCEL' }
  | { type: 'RESET_ERROR' };

export interface MachineState {
  phase: NavPhase;
  route: Route | null;
  destination: Coordinate | null;
  travelMode: TravelMode | null;
  rerouting: boolean;
  error: string | null;
}

export const EMPTY_MACHINE_STATE: MachineState = {
  phase: 'idle',
  route: null,
  destination: null,
  travelMode: null,
  rerouting: false,
  error: null,
};

function withRouteAndPhase(
  prev: MachineState,
  phase: NavPhase,
  route: Route,
  extra?: Partial<MachineState>,
): MachineState {
  return {
    ...prev,
    ...extra,
    phase,
    route,
  };
}

const NAVIGATING_PHASES: ReadonlySet<NavPhase> = new Set([
  'starting',
  'navigating',
  'degraded',
  'lost',
  'recovering',
  'rerouting',
]);

export function navigationMachine(prev: MachineState, event: NavEvent): MachineState {
  switch (event.type) {
    case 'SELECT_DESTINATION':
      return {
        phase: 'searching',
        route: null,
        destination: event.destination,
        travelMode: event.mode,
        rerouting: false,
        error: null,
      };

    case 'CALCULATE_ROUTE':
      if (!prev.destination) return prev;
      return {
        ...prev,
        phase: 'calculating',
        error: null,
        rerouting: false,
      };

    case 'ROUTE_SUCCESS':
      return withRouteAndPhase(prev, 'routeReady', event.route, {
        rerouting: false,
        error: null,
      });

    case 'ROUTE_FAILURE':
      return {
        ...prev,
        phase: 'error',
        error: event.message,
        rerouting: false,
      };

    case 'START_NAVIGATION':
      if (!prev.route) return prev;
      return {
        ...prev,
        phase: 'starting',
        error: null,
        rerouting: false,
      };

    case 'POSITION_UPDATE':
      return reducePositionUpdate(prev, event);

    case 'STATUS_CHANGE':
      return reduceStatusChange(prev, event);

    case 'OFF_ROUTE_DETECTED':
      // A reroute will be triggered by the orchestrator once cooldown allows.
      if (!NAVIGATING_PHASES.has(prev.phase)) return prev;
      return { ...prev, phase: 'rerouting', rerouting: true, error: null };

    case 'REROUTE_SUCCESS':
      return withRouteAndPhase(prev, prev.phase === 'lost' ? 'recovering' : 'navigating', event.route, {
        rerouting: false,
        error: null,
      });

    case 'REROUTE_FAILURE':
      // Keep guiding on the existing route; just surface a soft warning.
      return {
        ...prev,
        phase: NAVIGATING_PHASES.has(prev.phase) ? prev.phase : 'navigating',
        rerouting: false,
        error: event.message,
      };

    case 'ARRIVED':
      return { ...prev, phase: 'arrived', rerouting: false };

    case 'CANCEL':
      return EMPTY_MACHINE_STATE;

    case 'RESET_ERROR':
      return { ...prev, error: null };

    default:
      return prev;
  }
}

function reducePositionUpdate(prev: MachineState, event: Extract<NavEvent, { type: 'POSITION_UPDATE' }>): MachineState {
  const status = event.status;

  // Arrived detection is signalled by the orchestrator (it has the progress).
  if (prev.phase === 'starting' && status === 'available') {
    return { ...prev, phase: 'navigating', error: null };
  }
  if ((prev.phase === 'recovering' || prev.phase === 'lost') && status === 'available') {
    return { ...prev, phase: 'navigating', error: null };
  }
  if (prev.phase === 'starting' && status === 'degraded') {
    // First fix arrived but accuracy is limited — still start guiding.
    return { ...prev, phase: 'navigating', error: null };
  }
  return prev;
}

function reduceStatusChange(prev: MachineState, event: Extract<NavEvent, { type: 'STATUS_CHANGE' }>): MachineState {
  const { status } = event;
  if (!NAVIGATING_PHASES.has(prev.phase) && prev.phase !== 'routeReady') {
    return prev;
  }

  switch (status) {
    case 'lost':
      return { ...prev, phase: 'lost' };
    case 'recovering':
      return { ...prev, phase: 'recovering' };
    case 'degraded':
      if (prev.phase === 'rerouting') return prev;
      return { ...prev, phase: 'degraded' };
    case 'available':
      if (prev.phase === 'routeReady') return prev;
      if (prev.phase === 'rerouting') return prev;
      return { ...prev, phase: 'navigating' };
    default:
      return prev;
  }
}