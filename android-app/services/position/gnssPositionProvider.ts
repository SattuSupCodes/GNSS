import * as Location from 'expo-location';
import { classifyGnssHealth, transitionGnssStatus } from '@/core/gnssHealth';
import type {
  GeoPosition,
  PermissionState,
  PositionChangeListener,
  PositionProvider,
  PositioningStatus,
} from '@/types/position';

/**
 * Real GNSS provider built on expo-location.
 *
 * Behavior:
 *  - requests foreground permission on start (user sees the OS dialog)
 *  - watches high-accuracy updates at ~1s / 3m
 *  - classifies health (available/degraded/lost) from fix age + accuracy
 *  - never fabricates data: no fix → `getCurrentPosition()` returns null
 *  - when the fix goes stale, health is re-evaluated on a watchdog timer
 */

const WATCH_OPTIONS: Location.LocationOptions = {
  accuracy: Location.Accuracy.High,
  distanceInterval: 3,
  timeInterval: 1000,
};

const HEALTH_POLL_MS = 4_000;

export class GnssPositionProvider implements PositionProvider {
  readonly providerId = 'gnss';
  readonly source = 'gnss' as const;

  private current: GeoPosition | null = null;
  private status: PositioningStatus = 'lost';
  private permission: PermissionState = 'undetermined';
  private lastFixMillis: number | null = null;
  private recoveringUntil: number | null = null;
  private listeners = new Set<PositionChangeListener>();
  private subscription: Location.LocationSubscription | null = null;
  private healthTimer: ReturnType<typeof setInterval> | null = null;
  private started = false;

  getPermissionState(): PermissionState {
    return this.permission;
  }

  getStatus(): PositioningStatus {
    return this.status;
  }

  getCurrentPosition(): GeoPosition | null {
    return this.current;
  }

  subscribe(listener: PositionChangeListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  async requestPermission(): Promise<PermissionState> {
    let status: Location.PermissionStatus = Location.PermissionStatus.UNDETERMINED;
    try {
      ({ status } = await Location.requestForegroundPermissionsAsync());
    } catch {
      this.permission = 'unavailable';
      return this.permission;
    }
    if (status === 'granted') {
      this.permission = 'granted';
    } else if (status === 'denied') {
      this.permission = 'denied';
    } else {
      this.permission = 'undetermined';
    }
    return this.permission;
  }

  async start(): Promise<void> {
    if (this.started) return;
    this.started = true;

    if (this.permission !== 'granted') {
      await this.requestPermission();
    }

    if (this.permission !== 'granted') {
      this.setStatus('lost');
      return;
    }

    try {
      this.subscription = await Location.watchPositionAsync(WATCH_OPTIONS, (location) => {
        this.handleLocation(location);
      });
    } catch {
      this.setStatus('lost');
    }

    this.healthTimer = setInterval(() => this.reevaluateHealth(), HEALTH_POLL_MS);
  }

  stop(): void {
    if (!this.started) return;
    this.started = false;
    this.subscription?.remove();
    this.subscription = null;
    if (this.healthTimer) {
      clearInterval(this.healthTimer);
      this.healthTimer = null;
    }
  }

  private handleLocation(location: Location.LocationObject): void {
    const now = Date.now();
    const coords = location.coords;
    const classified = classifyGnssHealth({
      lastFixMillis: location.timestamp,
      accuracyMeters: coords.accuracy,
      now,
    });
    const transition = transitionGnssStatus(
      this.status,
      classified,
      now,
      this.recoveringUntil,
    );

    this.lastFixMillis = location.timestamp;
    this.recoveringUntil = transition.recoveringUntil;
    this.setStatus(transition.status);

    this.current = {
      latitude: coords.latitude,
      longitude: coords.longitude,
      altitude: coords.altitude,
      accuracy: coords.accuracy,
      speed: coords.speed,
      heading: coords.heading,
      timestamp: location.timestamp,
      source: 'gnss',
      status: transition.status,
    };

    this.emit();
  }

  private reevaluateHealth(): void {
    const classified = classifyGnssHealth({
      lastFixMillis: this.lastFixMillis,
      accuracyMeters: this.current?.accuracy ?? null,
      now: Date.now(),
    });
    const transition = transitionGnssStatus(this.status, classified, Date.now(), this.recoveringUntil);
    this.recoveringUntil = transition.recoveringUntil;
    const changed = this.setStatus(transition.status);
    if (changed && this.current) {
      this.current = { ...this.current, status: transition.status };
    }
    if (this.current && this.status !== 'lost') {
      // Status-only change was already flagged; current payload status synced.
      if (this.current.status !== transition.status) {
        this.current = { ...this.current, status: transition.status };
        this.emit();
      }
    } else if (this.status === 'lost' && this.current) {
      // Keep informing UI of the degraded payload even though no fix changed.
    }
  }

  private setStatus(status: PositioningStatus): boolean {
    if (this.status === status) return false;
    this.status = status;
    this.emit();
    return true;
  }

  private emit(): void {
    const position = this.current;
    for (const listener of this.listeners) {
      listener(position);
    }
  }
}