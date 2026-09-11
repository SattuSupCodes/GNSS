import { estimateEtaMillis, estimateRemainingSeconds } from '@/core/eta';
import { navigationMachine, EMPTY_MACHINE_STATE, type MachineState, type NavEvent } from '@/core/navigationMachine';
import { computeRouteProgress } from '@/core/routeProgress';
import { getHeadingEstimator } from '@/services/heading/headingEstimator';
import { subscribeSensor } from '@/services/sensors/sensorManager';
import type { RoutingService } from '@/services/routing/routingService';
import type { SpeedEstimator } from '@/services/speed/speedEstimator';
import type { AppSettings } from '@/types/settings';
import type { GeoPosition, PositionProvider } from '@/types/position';
import type { Coordinate, Route, TravelMode } from '@/types/routing';
import type { NavigationSnapshot, NavPhase, RouteProgressSnapshot } from '@/types/navigation';

/**
 * Navigation orchestrator — owns the live navigation session.
 *
 * It listens to the position provider, drives the pure state machine, and
 * produces uniform snapshots for the UI. Sensors (magnetometer for heading
 * fallback) are engaged only while actively guiding.
 */

const SENSOR_SUPPORTED_KINDS = ['magnetometer'] as const;

function userSafeMessage(error: unknown): string {
  if (error instanceof Error && error.message && error.message.length > 0) {
    return error.message;
  }
  return 'Something went wrong. Please try again.';
}

const GUIDING_PHASES: ReadonlySet<NavPhase> = new Set([
  'starting',
  'navigating',
  'degraded',
  'lost',
  'recovering',
  'rerouting',
]);

export interface NavigationOrchestratorDeps {
  positionProvider: PositionProvider;
  routing: RoutingService;
  speedEstimator: SpeedEstimator;
  getSettings: () => AppSettings;
  now?: () => number;
}

export class NavigationOrchestrator {
  private machine: MachineState = EMPTY_MACHINE_STATE;
  private readonly listeners = new Set<(snapshot: NavigationSnapshot) => void>();
  private positionSubscription: (() => void) | null = null;
  private compassUnsubscribe: (() => void) | null = null;
  private latestPosition: GeoPosition | null = null;
  private progress: RouteProgressSnapshot | null = null;
  private etaMillis: number | null = null;
  private speedMps: number | null = null;
  private headingDeg: number | null = null;
  private rerouteInFlight = false;
  private lastRerouteAt = 0;
  private started = false;
  private readonly heading = getHeadingEstimator();

  constructor(private readonly deps: NavigationOrchestratorDeps) {}

  private now(): number {
    return this.deps.now?.() ?? Date.now();
  }

  getSnapshot(): NavigationSnapshot {
    return this.buildSnapshot();
  }

  subscribe(listener: (snapshot: NavigationSnapshot) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  start(): void {
    if (this.started) return;
    this.started = true;
    this.positionSubscription = this.deps.positionProvider.subscribe((position) => {
      this.handlePosition(position);
    });
    void this.deps.positionProvider.start().then(() => {
      this.latestPosition = this.deps.positionProvider.getCurrentPosition();
      this.emit();
    });
  }

  stop(): void {
    if (!this.started) return;
    this.started = false;
    this.positionSubscription?.();
    this.positionSubscription = null;
    this.deps.positionProvider.stop();
    this.disengageCompass();
  }

  async requestRoute(destination: Coordinate, mode: TravelMode): Promise<void> {
    this.dispatch({ type: 'SELECT_DESTINATION', destination, mode });
    await this.calculateRoute();
  }

  async retryRoute(): Promise<void> {
    if (!this.machine.destination) return;
    await this.calculateRoute();
  }

  startNavigation(): void {
    if (!this.machine.route) return;
    this.dispatch({ type: 'START_NAVIGATION' });
    this.engageCompass();
    // Kick the first progress computation so guidance starts immediately.
    this.handlePosition(this.deps.positionProvider.getCurrentPosition());
    this.emit();
  }

  cancelNavigation(): void {
    this.dispatch({ type: 'CANCEL' });
    this.progress = null;
    this.etaMillis = null;
    this.speedMps = null;
    this.headingDeg = null;
    this.disengageCompass();
    this.emit();
  }

  resetError(): void {
    this.dispatch({ type: 'RESET_ERROR' });
    this.emit();
  }

  /** The latest route the session is working with (for map overlays). */
  get route(): Route | null {
    return this.machine.route;
  }

  get phase(): NavPhase {
    return this.machine.phase;
  }

  // ---- internals -------------------------------------------------------

  private async calculateRoute(): Promise<void> {
    this.dispatch({ type: 'CALCULATE_ROUTE' });

    const origin = this.currentOrigin();
    const destination = this.machine.destination;
    if (!origin) {
      this.dispatch({
        type: 'ROUTE_FAILURE',
        message:
          'Current position is not available yet. Enable location and try again.',
      });
      return;
    }
    if (!destination) {
      this.dispatch({ type: 'ROUTE_FAILURE', message: 'No destination selected.' });
      return;
    }

    try {
      const result = await this.deps.routing.calculate({
        origin,
        destination,
        options: {
          travelMode: this.machine.travelMode ?? 'car',
          locale: 'en',
        },
      });
      const route = result.routes[0];
      if (!route) {
        throw new Error('The routing engine returned no route. Try a different destination.');
      }
      this.dispatch({ type: 'ROUTE_SUCCESS', route });
      // Reset guidance internals for a fresh preview.
      this.progress = null;
      this.etaMillis = null;
    } catch (error) {
      this.dispatch({ type: 'ROUTE_FAILURE', message: userSafeMessage(error) });
    }
    this.emit();
  }

  private currentOrigin(): Coordinate | null {
    const position = this.latestPosition ?? this.deps.positionProvider.getCurrentPosition();
    return position ? { latitude: position.latitude, longitude: position.longitude } : null;
  }

  private dispatch(event: NavEvent): void {
    this.machine = navigationMachine(this.machine, event);
    this.emit();
  }

  private handlePosition(position: GeoPosition | null): void {
    if (position) {
      this.latestPosition = position;
    }

    const status = this.deps.positionProvider.getStatus();
    const machineStatus = position?.status ?? status;

    const phase = this.machine.phase;

    if (GUIDING_PHASES.has(phase)) {
      const settings = this.deps.getSettings();
      const route = this.machine.route;
      if (position && route) {
        const previousOffRoute = this.progress?.offRoute ?? false;
        this.progress = computeRouteProgress({
          route,
          point: { latitude: position.latitude, longitude: position.longitude },
          offRouteThresholdMeters: settings.navigation.rerouteThresholdMeters,
          arrivalThresholdMeters: settings.navigation.arrivalThresholdMeters,
          previouslyOffRoute: previousOffRoute,
        });
      }

      if (this.progress) {
        const remaining = estimateRemainingSeconds({
          route: this.machine.route!,
          progress: this.progress,
          currentSpeedMps: position?.speed ?? null,
          now: this.now(),
        });
        this.etaMillis = remaining > 0 ? this.now() + remaining * 1000 : null;
      }

      if (position) {
        this.speedMps = this.deps.speedEstimator.estimateSpeed().speedMps ?? position.speed;
      }
    }

    // Heading: prefer GNSS course; falls back to compass while stationary.
    const heading = this.heading.update(position ?? this.latestPosition);
    this.headingDeg = heading.headingDeg;

    // Drive the state machine (starting → navigating, recovered, etc.).
    this.dispatch({ type: 'POSITION_UPDATE', status: machineStatus });

    const currentPhase = this.machine.phase;
    if (this.progress?.offRoute && GUIDING_PHASES.has(currentPhase)) {
      this.maybeRequestReroute();
    } else if (this.progress?.arrived && GUIDING_PHASES.has(currentPhase)) {
      this.dispatch({ type: 'ARRIVED' });
      this.disengageCompass();
    }

    this.emit();
  }

  // ---- rerouting -------------------------------------------------------

  private maybeRequestReroute(): void {
    if (this.rerouteInFlight) return;
    const settings = this.deps.getSettings();
    if (!settings.navigation.rerouteEnabled) return;
    if (this.machine.phase === 'lost') return;

    const cooldownMs = settings.navigation.rerouteCooldownSeconds * 1000;
    const now = this.now();
    if (now - this.lastRerouteAt < cooldownMs) return;
    this.lastRerouteAt = now;

    this.dispatch({ type: 'OFF_ROUTE_DETECTED' });
    void this.runReroute();
  }

  private async runReroute(): Promise<void> {
    const route = this.machine.route;
    const destination = this.machine.destination;
    const origin = this.currentOrigin();
    if (!route || !destination || !origin) {
      this.rerouteInFlight = false;
      this.dispatch({ type: 'REROUTE_FAILURE', message: 'Could not reroute — position unavailable.' });
      this.emit();
      return;
    }

    this.rerouteInFlight = true;
    try {
      const result = await this.deps.routing.calculate({
        origin,
        destination,
        options: { travelMode: this.machine.travelMode ?? 'car', locale: 'en' },
      });
      const next = result.routes[0];
      if (!next) {
        throw new Error('The routing engine returned no route for rerouting.');
      }
      this.progress = null;
      this.etaMillis = null;
      this.dispatch({ type: 'REROUTE_SUCCESS', route: next });
    } catch (error) {
      this.dispatch({ type: 'REROUTE_FAILURE', message: userSafeMessage(error) });
    } finally {
      this.rerouteInFlight = false;
    }
    this.emit();
  }

  // ---- compass ---------------------------------------------------------

  private engageCompass(): void {
    if (this.compassUnsubscribe) return;
    void subscribeSensor('magnetometer', (reading) => {
      // Convert magnetic to a heading estimate via planar YX (device flat).
      const heading = (Math.atan2(-reading.y, reading.x) * 180) / Math.PI;
      const normalized = (heading + 360) % 360;
      this.heading.feedCompass(normalized);
    }, 200)
      .then((unsubscribe) => {
        if (GUIDING_PHASES.has(this.machine.phase)) {
          this.compassUnsubscribe = unsubscribe;
        } else {
          unsubscribe();
        }
      })
      .catch(() => {
        // Compass unavailable — heading stays GNSS-course only.
      });
  }

  private disengageCompass(): void {
    this.compassUnsubscribe?.();
    this.compassUnsubscribe = null;
    this.heading.reset();
  }

  // ---- snapshot --------------------------------------------------------

  private buildSnapshot(): NavigationSnapshot {
    const route = this.machine.route;
    const guiding = GUIDING_PHASES.has(this.machine.phase);
    const position = this.latestPosition ?? this.deps.positionProvider.getCurrentPosition();

    return {
      phase: this.machine.phase,
      route,
      destination: this.machine.destination,
      travelMode: this.machine.travelMode,
      position,
      positioningStatus: this.deps.positionProvider.getStatus(),
      positionSource: position?.source ?? 'unknown',
      progress: guiding ? this.progress : null,
      etaMillis: guiding ? this.etaMillis : null,
      speedMps: guiding ? this.speedMps : null,
      headingDeg: this.headingDeg,
      rerouting: this.machine.rerouting && this.machine.phase === 'rerouting',
      error: this.machine.phase === 'error' ? this.machine.error : null,
    };
  }

  private emit(): void {
    const snapshot = this.buildSnapshot();
    for (const listener of this.listeners) {
      listener(snapshot);
    }
  }
}

// ---- process-wide singleton ----------------------------------------------

let sharedOrchestrator: NavigationOrchestrator | null = null;

export function getSharedOrchestrator(deps: NavigationOrchestratorDeps): NavigationOrchestrator {
  if (!sharedOrchestrator) {
    sharedOrchestrator = new NavigationOrchestrator(deps);
    sharedOrchestrator.start();
  }
  return sharedOrchestrator;
}

export function resetSharedOrchestrator(): void {
  sharedOrchestrator?.stop();
  sharedOrchestrator = null;
}