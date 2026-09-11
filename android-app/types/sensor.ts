export type SensorKind = 'accelerometer' | 'gyroscope' | 'magnetometer';

export interface SensorReading {
  kind: SensorKind;
  x: number;
  y: number;
  z: number;
  /** Epoch seconds (native sensor clock). Use only for deltas. */
  timestamp: number;
}

export type SensorReadingListener = (reading: SensorReading) => void;
export type Unsubscribe = () => void;