# IDR Navigation — React Native + Expo Mobile Client

**Smart India Hackathon 2026 — Problem Statement: "AI-ML based Intelligent Dead Reckoning system for seamless navigation"**
**Organization: Indian Space Research Organisation (ISRO)**

---

## 1. What This Application Is

This directory (`android-app/`) is the **React Native + Axios + Expo mobile client** for the SIH 2026 Intelligent Dead Reckoning (IDR) project. It will eventually transform a smartphone into a vehicle positioning system that maintains accurate navigation during GNSS-denied environments (tunnels, urban canyons, parking structures) using **only smartphone-generated sensor data**.

The companion Python backend (data pipeline, calibration, models, IDR engine) lives in the repo root. This directory is intentionally an **empty structural skeleton** — the two will be connected in a later phase.

## 2. Runtime Constraint (Smartphone-Only)

The runtime system MUST rely ONLY on the smartphone:

- Accelerometer
- Gyroscope
- Magnetometer / compass
- Smartphone GNSS / GPS
- Sensor timestamps

The system must NEVER depend on vehicle hardware:

- NO OBD-II / CAN / ECU
- NO wheel-speed sensors
- NO vehicle telemetry
- NO vehicle GPS
- NO vehicle IMU
- NO physical connection to the vehicle

## 3. Current Development Workflow

- **Expo Go** is used for development and testing.
- The project is a **standard Expo managed workflow** application (no ejected/native code).
- No native Android/iOS source directories exist — none will be added at this stage.

## 4. Planned Future Stack

| Component | Purpose | Status |
|-----------|---------|--------|
| React Native + Expo | Cross-platform app shell | ✅ Skeleton created |
| Expo Router | File-based navigation | ✅ Skeleton in place |
| MapLibre Native | Map rendering (MapView, markers, route layer) | 🔲 Future integration |
| GraphHopper | Routing, turn instructions, map matching | 🔲 Future integration |
| IDR Engine | Smartphone-only positioning & dead reckoning | 🔲 Future integration |
| Smartphone sensors | Accelerometer / gyro / magnetometer ingestion | 🔲 Future integration |
| Smartphone GNSS | Location provider / GNSS availability | 🔲 Future integration |
| AI/ML models | Speed / kinematic estimation and corrections | 🔲 Future integration (Python side) |

## 5. Intended Future Architecture

```
Smartphone Sensors (accel / gyro / mag / timestamps)
       |
       v
  IDR Engine             <-- smartphone-only positioning
       |
       v
  Position Provider      <-- unified GNSS + DR position stream
       |
       +---------> MapLibre (map rendering + current-position layer)
       |
       +---------> Navigation State (position / velocity / heading + confidence)
       |
       v
GraphHopper Routing     <-- route geometry, turn instructions, map matching
       |
       v
  Navigation UI
```

GraphHopper and MapLibre are **future integrations** only. Neither is installed, configured, or referenced by any code at this point.

## 6. Current Repository State

This is **ONLY a skeleton**.

The following have **NOT been implemented**:

- ✗ Navigation logic
- ✗ Sensor access / sensor streaming
- ✗ GNSS / location logic
- ✗ IDR engine integration
- ✗ MapLibre integration
- ✗ GraphHopper / routing integration
- ✗ AI/ML model integration
- ✗ Backend (Python) connectivity

The application does not yet produce, consume, or persist any navigation data.

## 7. Folder Map

### `app/` — Expo Router application layer (route-scoped)

| Folder | Future Responsibility |
|--------|------------------------|
| `app/(tabs)` | Application tab routes (placeholder test tab) |
| `app/navigation/` | Navigation orchestration: session, route following, GNSS/IDR mode |
| `app/map/` | MapLibre integration: MapView, configuration, markers, route rendering, camera, current position |
| `app/location/` | Location abstraction: GNSS provider, permissions, availability, current position |
| `app/idr/` | IDR engine adapter: position provider, navigation state, confidence, GNSS/DR switching |
| `app/sensors/` | Sensor ingestion: accelerometer, gyroscope, magnetometer, timestamps, stream abstraction |
| `app/routing/` | GraphHopper integration: route requests, results, geometry, turn instructions, map matching |
| `app/components/` | Reusable application-specific React components |
| `app/screens/` | Screen-level components |
| `app/services/` | Service abstractions for external/native integrations |
| `app/state/` | Global state management (provider/framework not yet chosen) |
| `app/types/` | TypeScript interfaces (Position, Heading, Velocity, NavigationState, SensorSample, GNSSSample, Route, IDR state) |
| `app/utils/` | Route-scoped utilities |
| `app/config/` | Application configuration (future) |

### Root-level folders — shared, app-wide architecture placeholders

| Folder | Future Responsibility |
|--------|------------------------|
| `components/` | Shared React components usable across the whole app |
| `constants/` | App-wide constants (theme, config values) |
| `hooks/` | Shared React hooks |
| `lib/` | Shared internal libraries / integrations |
| `services/` | App-wide service abstractions |
| `types/` | App-wide TypeScript types |
| `utils/` | App-wide utilities |

> These root-level folders and the `app/*` folders are **mutually exclusive by scope**: root-level folders hold app-wide shared code, `app/*` holds route-scoped code. No functionality is duplicated between them; they are architectural placeholders for now.

### `assets/` — static assets

| Folder | Purpose |
|--------|---------|
| `assets/images/` | App icons and splash images (referenced by `app.json`) |
| `assets/icons/` | Reserved for future icon assets |
| `assets/maps/` | Reserved for future offline map data (tiles, MBTiles, PBF). No map data is downloaded or committed. |

## 8. Getting Started

```bash
cd android-app
npm install
npm start        # then scan QR with Expo Go
npm run android  # or: npx expo start --android
```

## 9. Current Status

- ✅ Standard Expo managed workflow (SDK 57), TypeScript, compatible with Expo Go
- ✅ File-based routing structure in place (Expo Router)
- ✅ Directory skeleton with placeholder markers for every planned module
- ⏳ Everything else is future work

No navigation logic, sensor logic, GNSS logic, IDR integration, MapLibre integration, or GraphHopper integration has been implemented yet.
