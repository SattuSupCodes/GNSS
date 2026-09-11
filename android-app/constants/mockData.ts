/**
 * UI fixture data.
 *
 * Everything in this file is STATIC SAMPLE CONTENT used only to preview the
 * interface (Stitch design adaptation). It is intentionally isolated here so a
 * future engineering phase can replace it with real services (routing API,
 * GNSS/IDR providers, sensor pipeline) without touching any screen code.
 */

import type { IconName } from '@/components/Icon';
import type { MetricTone } from '@/components/Metrics';

export interface CategoryChipData {
  id: string;
  label: string;
  icon: IconName;
}

export const homeCategories: CategoryChipData[] = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'work', label: 'Work', icon: 'work' },
  { id: 'restaurants', label: 'Restaurants', icon: 'restaurant' },
  { id: 'fuel', label: 'Fuel', icon: 'fuel' },
  { id: 'parking', label: 'Parking', icon: 'parking' },
  { id: 'coffee', label: 'Coffee', icon: 'coffee' },
];

export interface RouteModeData {
  id: string;
  label: string;
  icon: IconName;
  duration: string;
}

export const routeModes: RouteModeData[] = [
  { id: 'car', label: 'Car', icon: 'car', duration: '24 min' },
  { id: 'transit', label: 'Transit', icon: 'transit', duration: '42 min' },
  { id: 'walk', label: 'Walk', icon: 'walk', duration: '2 hr 40 min' },
  { id: 'bike', label: 'Bike', icon: 'bike', duration: '52 min' },
];

export interface PlaceData {
  id: string;
  name: string;
  address: string;
  category: string;
  sublabel?: string;
}

export const recentDestinations: PlaceData[] = [
  { id: 'iit-delhi', name: 'IIT Delhi', address: 'Hauz Khas, New Delhi', category: 'Campus' },
  { id: 'cp', name: 'Connaught Place', address: 'New Delhi', category: 'Shopping' },
  { id: 'airport', name: 'Indira Gandhi Int\u2019l Airport T3', address: 'Aerocity, New Delhi', category: 'Airport' },
];

export const searchResults: PlaceData[] = [
  {
    id: 'airport',
    name: 'Indira Gandhi Int\u2019l Airport T3',
    address: 'Aerocity, New Delhi',
    category: 'Airport',
    sublabel: 'Terminal 3 Departure Loop',
  },
  { id: 'iit-delhi', name: 'IIT Delhi', address: 'Hauz Khas, New Delhi', category: 'Campus' },
  { id: 'cp', name: 'Connaught Place', address: 'New Delhi', category: 'Shopping' },
  { id: 'akshardham', name: 'Akshardham Temple', address: 'Noida Link Road, Delhi', category: 'Heritage' },
  { id: 'hauz-khas', name: 'Hauz Khas Village', address: 'South Delhi', category: 'Dining' },
];

export interface RouteSummaryData {
  id: string;
  destinationId: string;
  originLabel: string;
  destinationLabel: string;
  mode: string;
  duration: string;
  distanceKm: string;
  eta: string;
  via: string;
  fastest: boolean;
  tip: string;
}

export const demoRoute: RouteSummaryData = {
  id: 'route-airport',
  destinationId: 'airport',
  originLabel: 'Current Location',
  destinationLabel: 'Indira Gandhi Int\u2019l Airport T3',
  mode: 'car',
  duration: '24 min',
  distanceKm: '14.8 km',
  eta: '11:02 AM',
  via: 'NH-48 & Sardar Patel Marg',
  fastest: true,
  tip: 'Seamless positioning through underpasses & tunnels',
};

export interface RouteStepData {
  id: string;
  icon: IconName;
  instruction: string;
  distance: string;
}

export const routeSteps: RouteStepData[] = [
  { id: 's1', icon: 'straight', instruction: 'Head north on Outer Ring Road', distance: '400 m' },
  { id: 's2', icon: 'turnRight', instruction: 'Keep right onto NH-48 Expressway', distance: '8.2 km' },
  { id: 's3', icon: 'forkRight', instruction: 'Take the exit towards Terminal 3', distance: '3.5 km' },
  { id: 's4', icon: 'turnRight', instruction: 'Turn right onto Terminal 3 Departure Loop', distance: '280 m' },
  { id: 's5', icon: 'destination', instruction: 'Arrive at the departure gate', distance: '0 m' },
];

export interface NavSessionData {
  destinationLabel: string;
  durationRemaining: string;
  distanceRemaining: string;
  eta: string;
  currentInstruction: string;
  currentDistance: string;
  next: { icon: IconName; label: string; distance: string };
  smoothFlow: string;
}

export const demoNavSession: NavSessionData = {
  destinationLabel: 'Airport T3',
  durationRemaining: '14 min',
  distanceRemaining: '8.4 km',
  eta: '11:02 AM',
  currentInstruction: 'Turn right onto Terminal 3 Departure Loop',
  currentDistance: '280 m',
  next: { icon: 'forkLeft', label: 'Then fork left towards Gate 1\u20134', distance: '600 m' },
  smoothFlow: 'Smooth Flow',
};

export interface RouteCardData {
  id: string;
  title: string;
  destinationLabel: string;
  duration: string;
  distanceKm: string;
  icon: IconName;
}

export const demoRouteCards: RouteCardData[] = [
  { id: 'r1', title: 'Fastest \u00b7 Fuel efficient', destinationLabel: 'IIT Delhi', duration: '18 min', distanceKm: '9.2 km', icon: 'route' },
  { id: 'r2', title: 'Scenic \u00b7 Less traffic', destinationLabel: 'Connaught Place', duration: '26 min', distanceKm: '12.4 km', icon: 'route' },
  { id: 'r3', title: 'Toll-free', destinationLabel: 'Akshardham Temple', duration: '31 min', distanceKm: '15.8 km', icon: 'route' },
];

export interface SavedPlaceData {
  id: string;
  name: string;
  address: string;
  icon: IconName;
}

export const savedPlaces: SavedPlaceData[] = [
  { id: 'home', name: 'Home', address: 'Saved home address', icon: 'home' },
  { id: 'work', name: 'Work', address: 'Saved work address', icon: 'work' },
  { id: 'airport', name: 'Indira Gandhi Int\u2019l Airport T3', address: 'Aerocity, New Delhi', icon: 'flight' },
];

export const diagnosticsDemo = {
  label: 'DEMO DATA',
  constellation: 'NavIC Dual-Freq L5/S',
  modeLabel: 'GNSS + IMU fusion preview',
  confidence: '96%',
  cep50: '1.8 m',
  accuracy: '2.4 m',
  satellites: '14',
  updateRate: '10 Hz',
};

export interface SensorDemoData {
  id: string;
  name: string;
  icon: IconName;
  state: string;
  tone: MetricTone;
}

export const sensorDemo: SensorDemoData[] = [
  { id: 'gyro', name: 'Gyroscope', icon: 'gyro', state: 'Calibrated', tone: 'ok' },
  { id: 'accel', name: 'Accelerometer', icon: 'motion', state: 'Calibrated', tone: 'ok' },
  { id: 'mag', name: 'Magnetometer', icon: 'magnetometer', state: 'Calibrated', tone: 'ok' },
  { id: 'baro', name: 'Barometer', icon: 'altimeter', state: 'Calibrated', tone: 'ok' },
  { id: 'fusion', name: 'Inertial fusion engine', icon: 'brain', state: 'Preview only', tone: 'demo' },
  { id: 'odom', name: 'Wheel odometry', icon: 'gauge', state: 'Preview only', tone: 'demo' },
];

export interface OfflineRegionData {
  id: string;
  name: string;
  sizeMb: string;
  available: boolean;
}

export const offlineRegions: OfflineRegionData[] = [
  { id: 'delhi', name: 'Delhi NCR', sizeMb: '128 MB', available: true },
  { id: 'noida', name: 'Noida & Greater Noida', sizeMb: '96 MB', available: true },
  { id: 'gurugram', name: 'Gurugram', sizeMb: '84 MB', available: false },
  { id: 'ghaziabad', name: 'Ghaziabad', sizeMb: '76 MB', available: false },
];