import { coordinateAtDistance } from '@/core/geo';
import type {
  GeoPosition,
  PermissionState,
  PositionChangeListener,
  PositionProvider,
  PositioningStatus,
} from '@/types/position';
import type { Coordinate } from '@/types/routing';

/**
 * DEMO-ONLY simulated position provider.
 *
 * Drives a fake drive along a synthetic path so the navigation UI can be
 * exercised without a device/GPS. It is never used in production wiring —
 * everything it emits is explicitly a simulation:
 *  - reported coordinates come from interpolation along `path`
 *  - status toggles are synthetic
 *  - `getPermissionState()` reports granted (no OS dialog)
 */
export class DemoPositionProvider implements PositionProvider {
  readonly providerId = 'demo-sim';
  readonly source = 'unknown' as const;

  private readonly listeners = new Set<PositionChangeListener>();
  private current: GeoPosition | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private origin: Coordinate;
  private bearingDeg: number;
  private speedMps = 9; // ~32 km/h simulated cruise
  private traveled = 0;
  private degraded = false;

  constructor(path: Coordinate[]) {
    const effectivePath = path.length > 0 ? path : [{ latitude: 25.2048, longitude: 55.2708 }];
    this.origin = effectivePath[0];
    this.bearingDeg = this.initialBearing(effectivePath);
    this.traveled = 0;
  }

  private initialBearing(path: Coordinate[]): number {
    if (path.length < 2) return 0;
    const [a, b] = path;
    const y = Math.sin(toRad(b.longitude - a.longitude)) * Math.cos(toRad(b.latitude));
    const x =
      Math.cos(toRad(a.latitude)) * Math.sin(toRad(b.latitude)) -
      Math.sin(toRad(a.latitude)) * Math.cos(toRad(b.latitude)) * Math.cos(toRad(b.longitude - a.longitude));
    return (toDeg(Math.atan2(y, x)) + 360) % 360;
  }

  getPermissionState(): PermissionState {
    return 'granted';
  }

  getStatus(): PositioningStatus {
    return this.degraded ? 'degraded' : 'available';
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

  requestPermission(): Promise<PermissionState> {
    return Promise.resolve('granted');
  }

  start(): Promise<void> {
    this.timer = setInterval(() => this.tick(), 1000);
    this.tick();
    return Promise.resolve();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  private tick(): void {
    // Simulate drift: modulate speed each tick.
    this.speedMps = Math.max(2, this.speedMps + (Math.random() - 0.5) * 3);
    const next = coordinateAtDistance(
      [this.origin, stepCoordinate(this.origin, this.bearingDeg, 4000)],
      this.traveled,
    );
    this.traveled += this.speedMps;
    // Wrap the "drive" for a long-running demo.
    if (this.traveled > 3800) {
      this.traveled = 0;
    }

    this.current = {
      ...next,
      altitude: null,
      accuracy: this.degraded ? 95 : 6,
      speed: this.speedMps,
      heading: this.bearingDeg,
      timestamp: Date.now(),
      source: 'unknown',
      status: this.degraded ? 'degraded' : 'available',
    };
    for (const listener of this.listeners) {
      listener(this.current);
    }
  }

  setDegraded(flag: boolean): void {
    this.degraded = flag;
    if (this.current) {
      this.current = { ...this.current, status: flag ? 'degraded' : 'available', accuracy: flag ? 95 : 6 };
    }
  }
}

function toRad(d: number): number {
  return (d * Math.PI) / 180;
}
function toDeg(r: number): number {
  return (r * 180) / Math.PI;
}
function stepCoordinate(origin: Coordinate, bearingDeg: number, meters: number): Coordinate {
  const R = 6_371_008.8;
  const brng = toRad(bearingDeg);
  const d = meters / R;
  const lat1 = toRad(origin.latitude);
  const lon1 = toRad(origin.longitude);
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(d) + Math.cos(lat1) * Math.sin(d) * Math.cos(brng),
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(brng) * Math.sin(d) * Math.cos(lat1),
      Math.cos(d) - Math.sin(lat1) * Math.sin(lat2),
    );
  return { latitude: toDeg(lat2), longitude: toDeg(lon2) };
}