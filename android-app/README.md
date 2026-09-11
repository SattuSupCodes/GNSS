# NavSphere — React Native + Expo Mobile Client

**Smart India Hackathon 2026 — Problem Statement: "AI-ML based Intelligent Dead Reckoning system for seamless navigation"**
**Organization: Indian Space Research Organisation (ISRO)**

The mobile client for the SIH 2026 Intelligent Dead Reckoning (IDR) project.
This is a **working navigation app**: live GNSS positioning, real routing and
geocoding, turn-by-turn guidance, route preview, saved places, honest GNSS
health/loss handling, settings, and diagnostics.

---

## 1. What This Build Includes

| Capability | Status |
|-----------|--------|
| Live GNSS positioning (`expo-location`, foreground watch) | ✅ |
| GNSS health classification: available / degraded / lost / recovering | ✅ |
| Map — MapLibre native (OpenFreeMap styles + satellite) | ✅ native dev build |
| Map — web fallback (labeled preview) | ✅ |
| Routing + geocoding (GraphHopper API) | ✅ with key |
| Turn-by-turn guidance (maneuvers, speed, ETA, reroute, arrive) | ✅ |
| Route preview with mode switching (drive / walk / cycle) | ✅ |
| Saved places + recent searches (persisted) | ✅ |
| Settings: map style, follow-user, reroute, privacy | ✅ |
| Diagnostics screen with real telemetry | ✅ |
| Unit tests for all navigation math | ✅ |

### Placeholder contracts (clearly labeled, never fabricated)

Per the problem statement, smartphone-only sensor fusion (IDR) and AI/ML
speed models are defined interfaces. In this build:

- `idr` / `hybrid` position providers exist as interfaces but always report
  **no fix**; they are only reachable via the explicitly-labeled **Demo**
  toggle and are never claimed to be active.
- `MLSpeedEstimator` / `SensorSpeedEstimator` always return `null`; displayed
  speed comes from real GPS speed.
- When the fix is lost the app says exactly that:
  **"GPS signal lost — waiting for a stronger signal."**

The companion Python backend lives in the repo root; this app treats it as an
external contract (see IDR modeling work) and does not bundle it.

## 2. Runtime Constraint (Smartphone-Only)

The runtime system relies ONLY on the smartphone: accelerometer, gyroscope,
magnetometer/compass, GNSS, and sensor timestamps. It never depends on vehicle
hardware (no OBD-II/CAN/ECU, no vehicle GPS/IMU, no physical connection).

## 3. Getting Started

```bash
cd android-app
npm install
cp .env.example .env     # then add your GraphHopper API key
npm start
```

- **Native map + location require a development build** because
  `@maplibre/maplibre-react-native` and `expo-location` are native modules:
  `npx expo run:android` (or an EAS build). Expo Go cannot run MapLibre.
- Without a GraphHopper key the app still runs; routing/search surfaces a
  user-safe "not configured" message instead of fake data.

## 4. Project Map

| Folder | Purpose |
|--------|---------|
| `app/` | Expo Router screens (tabs, search, place, routing, navigation, settings) |
| `components/` | Reusable UI + map wrappers |
| `config/` | Env + map style registry |
| `constants/` | Theme tokens |
| `core/` | Pure navigation logic (geo, health, progress, ETA, state machine) |
| `services/` | Storage, position providers, sensors, routing/search |
| `state/` | Navigation orchestrator + provider |
| `types/` | Domain models |
| `utils/` | Formatters + icon mapping |
| `docs/` | Architecture documentation |
| `__tests__/` | Jest unit tests |

## 5. Scripts

```bash
npm run start           # expo start
npm run android         # expo start --android
npm run web             # expo start --web
npm test                # jest unit tests
npx tsc --noEmit        # type check
npx expo export --platform web   # web bundle smoke-test
```

## 6. See Also

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module design, positioning
  truthfulness model, state machine.
- `.env.example` — full configuration reference.