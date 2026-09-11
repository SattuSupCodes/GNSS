import { Accelerometer, Gyroscope, Magnetometer } from 'expo-sensors';
import type { EventSubscription } from 'expo-modules-core';
import type {
  SensorKind,
  SensorReading,
  SensorReadingListener,
} from '@/types/sensor';

/**
 * Sensor stream manager (accelerometer / gyroscope / magnetometer).
 *
 * Sensors are only subscribed while navigation is active — the UI never
 * touches expo-sensors directly. Consumers receive normalized, timestamped
 * readings via subscribeSensor.
 */

export interface RawMeasurement {
  x?: number;
  y?: number;
  z?: number;
  /** Epoch seconds (device clock). Use only for deltas. */
  timestamp?: number;
}

interface SensorModuleHandle {
  addListener(listener: (measurement: RawMeasurement) => void): EventSubscription;
  setUpdateInterval(intervalMs: number): void;
  isAvailableAsync(): Promise<boolean>;
  removeAllListeners(): void;
}

const MODULES: Record<SensorKind, SensorModuleHandle> = {
  accelerometer: Accelerometer,
  gyroscope: Gyroscope,
  magnetometer: Magnetometer,
};

const DEFAULT_INTERVAL_MS = 100;

export function isSensorAvailable(kind: SensorKind): Promise<boolean> {
  try {
    return MODULES[kind].isAvailableAsync();
  } catch {
    return Promise.resolve(false);
  }
}

/**
 * Subscribe to a sensor stream. Resolves an unsubscribe function once the
 * native subscription is established.
 */
export function subscribeSensor(
  kind: SensorKind,
  listener: SensorReadingListener,
  intervalMs = DEFAULT_INTERVAL_MS,
): Promise<() => void> {
  const module = MODULES[kind];
  const callback = (measurement: RawMeasurement) => {
    listener({
      kind,
      x: Number(measurement.x) || 0,
      y: Number(measurement.y) || 0,
      z: Number(measurement.z) || 0,
      timestamp: measurement.timestamp ?? 0,
    });
  };

  module.setUpdateInterval(intervalMs);
  const subscription = module.addListener(callback);
  return Promise.resolve(() => subscription.remove());
}

export function stopAllSensors(): void {
  Accelerometer.removeAllListeners();
  Gyroscope.removeAllListeners();
  Magnetometer.removeAllListeners();
}