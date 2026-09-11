import { readJson, writeJson } from '@/services/storage';
import { DEFAULT_SETTINGS } from '@/types/settings';
import type { AppSettings } from '@/types/settings';

/**
 * Persisted application settings. A module-level cache plus micro-subscriber
 * loop keeps the UI reactive without pulling a state library into this seam.
 */

export const SETTINGS_KEY = 'navsphere.settings';

let cache: AppSettings | null = null;
let loadPromise: Promise<AppSettings> | null = null;

type SettingsListener = (settings: AppSettings) => void;
const listeners = new Set<SettingsListener>();

export async function loadSettings(): Promise<AppSettings> {
  if (cache) return cache;
  if (!loadPromise) {
    loadPromise = readJson<AppSettings>(SETTINGS_KEY, DEFAULT_SETTINGS).then((loaded) => {
      cache = { ...loaded };
      return cache;
    });
  }
  return loadPromise;
}

export function getCachedSettings(): AppSettings {
  return cache ?? DEFAULT_SETTINGS;
}

export function subscribeSettings(listener: SettingsListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export async function saveSettings(settings: AppSettings): Promise<void> {
  cache = { ...settings };
  await writeJson(SETTINGS_KEY, settings);
  for (const listener of listeners) {
    listener(cache);
  }
}

/** Update a partial slice of settings, persisting and notifying. */
export async function updateSettings(patch: Partial<AppSettings>): Promise<AppSettings> {
  const current = { ...getCachedSettings() };
  const next: AppSettings = {
    map: { ...current.map, ...(patch.map ?? {}) },
    navigation: { ...current.navigation, ...(patch.navigation ?? {}) },
    privacy: { ...current.privacy, ...(patch.privacy ?? {}) },
  };
  await saveSettings(next);
  return next;
}