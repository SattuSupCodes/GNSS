import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { env, isGraphHopperConfigured } from '@/config/env';
import { demoRoutingService } from '@/services/routing/demoRoutingService';
import { routingService } from '@/services/routing/routingService';
import { GnssSpeedEstimator, type SpeedEstimator } from '@/services/speed/speedEstimator';
import { createDefaultPositionProvider, createDemoPositionProvider } from '@/services/position';
import { getCachedSettings, loadSettings, subscribeSettings, updateSettings } from '@/services/settingsStore';
import {
  getSharedOrchestrator,
  NavigationOrchestrator,
  type NavigationOrchestratorDeps,
} from '@/state/navigation/navigationOrchestrator';
import type { AppSettings } from '@/types/settings';
import type { PositionProvider } from '@/types/position';
import type { Coordinate, TravelMode } from '@/types/routing';
import type { NavigationSnapshot } from '@/types/navigation';

/**
 * Navigation session provider — the single React seam between screens and the
 * navigation system. Wraps the orchestrator (state machine + providers) and
 * settings store with a render-friendly context.
 */

function buildLiveDeps(): NavigationOrchestratorDeps {
  const positionProvider: PositionProvider = createDefaultPositionProvider();
  const speed = new GnssSpeedEstimator(positionProvider);
  return {
    positionProvider,
    routing: routingService,
    speedEstimator: speed as SpeedEstimator,
    getSettings: getCachedSettings,
  };
}

function buildDemoDeps(): NavigationOrchestratorDeps {
  const positionProvider = createDemoPositionProvider([
    { latitude: 25.0782, longitude: 55.1321 },
    { latitude: 25.0801, longitude: 55.1391 },
    { latitude: 25.0811, longitude: 55.1451 },
  ]);
  const speed = new GnssSpeedEstimator(positionProvider as unknown as PositionProvider);
  return {
    positionProvider: positionProvider as unknown as PositionProvider,
    routing: demoRoutingService,
    speedEstimator: speed,
    getSettings: getCachedSettings,
  };
}

let demoOrchestrator: NavigationOrchestrator | null = null;

function getDemoOrchestrator(): NavigationOrchestrator {
  if (!demoOrchestrator) {
    demoOrchestrator = new NavigationOrchestrator(buildDemoDeps());
    demoOrchestrator.start();
  }
  return demoOrchestrator;
}

export interface NavigationActions {
  requestRoute(destination: Coordinate, mode: TravelMode): Promise<void>;
  retryRoute(): Promise<void>;
  startNavigation(): void;
  cancelNavigation(): void;
  resetError(): void;
  setDemoMode(mode: boolean): void;
  updateSettings(patch: Partial<AppSettings>): Promise<void>;
}

interface NavigationContextValue {
  snapshot: NavigationSnapshot;
  settings: AppSettings;
  demoMode: boolean;
  configureForRouting: boolean;
  actions: NavigationActions;
}

const NavigationContext = createContext<NavigationContextValue | null>(null);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [demoMode, setDemoMode] = useState(false);
  const [settings, setSettings] = useState<AppSettings>(getCachedSettings());
  const [snapshot, setSnapshot] = useState<NavigationSnapshot>(
    getSharedOrchestrator(buildLiveDeps()).getSnapshot(),
  );

  // Load & subscribe to persisted settings.
  useEffect(() => {
    loadSettings().then(setSettings);
    return subscribeSettings(setSettings);
  }, []);

  // Subscribe to the active orchestrator (live vs demo).
  useEffect(() => {
    const orchestrator = demoMode ? getDemoOrchestrator() : getSharedOrchestrator(buildLiveDeps());
    setSnapshot(orchestrator.getSnapshot());
    return orchestrator.subscribe(setSnapshot);
  }, [demoMode]);

  const actions = useMemo<NavigationActions>(
    () => ({
      requestRoute: async (destination, mode) => {
        const orchestrator = demoMode ? getDemoOrchestrator() : getSharedOrchestrator(buildLiveDeps());
        await orchestrator.requestRoute(destination, mode);
      },
      retryRoute: async () => {
        const orchestrator = demoMode ? getDemoOrchestrator() : getSharedOrchestrator(buildLiveDeps());
        await orchestrator.retryRoute();
      },
      startNavigation: () => {
        const orchestrator = demoMode ? getDemoOrchestrator() : getSharedOrchestrator(buildLiveDeps());
        orchestrator.startNavigation();
      },
      cancelNavigation: () => {
        const orchestrator = demoMode ? getDemoOrchestrator() : getSharedOrchestrator(buildLiveDeps());
        orchestrator.cancelNavigation();
      },
      resetError: () => {
        const orchestrator = demoMode ? getDemoOrchestrator() : getSharedOrchestrator(buildLiveDeps());
        orchestrator.resetError();
      },
      setDemoMode: (mode) => setDemoMode(mode),
      updateSettings: async (patch) => {
        await updateSettings(patch);
      },
    }),
    [demoMode],
  );

  const value = useMemo<NavigationContextValue>(
    () => ({
      snapshot,
      settings,
      demoMode,
      configureForRouting: isGraphHopperConfigured(),
      actions,
    }),
    [snapshot, settings, demoMode, actions],
  );

  return <NavigationContext.Provider value={value}>{children}</NavigationContext.Provider>;
}

export function useNavigationSession(): NavigationContextValue {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('useNavigationSession must be used within NavigationProvider');
  }
  return context;
}

export { env as navEnv };