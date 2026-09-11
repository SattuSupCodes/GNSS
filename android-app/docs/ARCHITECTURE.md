# NavSphere mobile app — Architecture

Live, production-oriented Expo (SDK 57) + React Native mobile client for the
SIH 2026 Intelligent Dead Reckoning (IDR) problem statement.

## Principles

- **Truthful positioning.** The app reports exactly what the smartphone knows.
  Lost fix → "GPS signal lost — waiting for a stronger signal". There is no
  fabricated "intelligent positioning" claim while no fusion is active.
- **Contract-only placeholders stay labeled.** Smartphone-only positioning
  providers (IDR, fused/hybrid) and AI/ML speed models are real interfaces with
  stubbed implementations that always report `not available`. They are only
  reachable through the explicitly-labeled **Demo** toggle and never claimed to
  be active.
- **Pure core, testable.** All navigation math lives in `core/` as pure
  functions with no I/O; the orchestrator wires them together. Unit tests run
  with Jest without touching native modules.
- **Never ship secrets.** All configuration is `EXPO_PUBLIC_*` (client-side by
  definition). Any future server credential must be proxied by a backend.

## Modules

```
components/   UI kit (buttons, cards, status banner, map wrappers)
config/       env + map style registry
constants/    theme tokens
core/         pure logic: geo, gnssHealth, routeProgress, eta, machine,
              normalization, places
services/     I/O: storage, position providers, sensors, heading/speed,
              routing + search (GraphHopper / demo)
state/        navigation orchestrator (singleton) + NavigationProvider
types/        domain models
utils/        formatters + icon mapping
app/          Expo Router screens
```

### Positioning

`types/position` defines:

- `PositioningStatus = available | degraded | lost | recovering`
- `PositionSource = gnss | idr | hybrid | unknown`
- `GeoPosition` carries latitude, longitude, altitude, accuracy, speed, heading,
  timestamp, source, status.

`services/position.ts` composes a `PositionProvider`. The GNSS provider wraps
`expo-location` (background-aware watch, accuracy scoring, heading from
magnetometer when available). Providers:

| Provider | Status |
|----------|--------|
| `gnssPositionProvider` | Live `expo-location` fixes |
| `idrPositionProvider` | Interface exists; always reports `lost`/null |
| `hybridPositionProvider` | Interface exists; always `lost`/null |
| `demoPositionProvider` | Playback of a synthetic trace, only via Demo toggle |

`core/gnssHealth` classifies a fix into strong/degraded/lost from freshness and
accuracy, and applies a `GNSS_RECOVERY_GRACE_MS` recovering window so the UI
does not flicker back to `available` the moment the first fix returns.

### Route + search

- GraphHopper client (`services/routing/routingService.ts`) hits `/route` and
  `/geocode` with the configured key. Missing key → `RoutingError('no_key')`
  with a user-safe message; the app never fabricates results.
- `core/routeNormalization` maps GraphHopper paths/instructions into the app
  `Route` model (geometry, maneuvers, bounds).
- `core/searchNormalization` maps geocoding hits into `SearchResult`.
- Demo providers sample synthetic data and are gated behind the Demo toggle.

### Navigation state machine

`core/navigationMachine` is a pure reducer over discrete events:

```
idle → searching → calculating → routeReady → starting
                                              → navigating → degraded / lost /
                                                             recovering / rerouting
                                                             → arrived
```

`state/navigation/navigationOrchestrator.ts` (singleton) drives the machine
from live inputs and computes a `NavigationSnapshot`:

- position + GNSS health status
- route progress (`core/routeProgress`): traveled distance along geometry,
  next maneuver, off-route detection with hysteresis
- ETA (`core/eta`): blends route-profile remaining time with live speed
- heading (`services/heading`): magnetometer + GPS course, wraparound-aware EMA
- speed (`services/speed`): GPS speed; ML/sensor estimators return null

Reroute: on `OFF_ROUTE_DETECTED` the orchestrator requests a new route after a
cooldown; success swaps the route, failure keeps guiding on the old one.

### Persistence (`services/`)

- `storage.ts` — typed AsyncStorage wrapper with JSON schema versioning.
- `placesStore.ts` — recent searches (LRU, de-duped) and saved places.
- `settingsStore.ts` — app settings (`AppSettings`): map style, follow-user,
  reroute toggles, thresholds, privacy.

### UI

Expo Router file-based routes. All screens read `useNavigationSession()`
(context from `state/NavigationProvider`). Map rendering:

- Native dev-build: `@maplibre/maplibre-react-native` `Map`/`Camera` with
  OpenFreeMap vector styles + a raster satellite style.
- Web: `components/maps/NavMap.web.tsx` — a clearly-labeled **preview** using a
  lightweight canvas projection (MapLibre native is not supported on web).

## Tests

`npm test` — Jest (jest-expo preset) against `core/` modules only (pure, no
native imports): geo, gnssHealth, routeProgress, eta, navigationMachine,
routeNormalization, searchNormalization, places.

## Validation

```bash
npx tsc --noEmit          # type check
npm test                  # unit tests
npx expo export --platform web   # web bundle smoke-test
```

Native testing requires a development build
(`expo run:android` / EAS build), since `@maplibre/maplibre-react-native`
requires native modules.