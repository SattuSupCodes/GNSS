/**
 * ThemeProvider — light / dark / system appearance with persistence.
 *
 * "System" follows the device appearance preference (via `useColorScheme`).
 * The resolved theme is consumed through `useTheme()`.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react';
import { useColorScheme, type ColorSchemeName } from 'react-native';

import { makeTheme, type AppearanceMode, type ThemeMode, type Theme } from '@/constants/theme';

const STORAGE_KEY = 'navsphere.appearanceMode';

export interface ThemeContextValue {
  /** Resolved theme (light or dark) driving every screen. */
  theme: Theme;
  /** User preference: system | light | dark. */
  appearance: AppearanceMode;
  setAppearance: (mode: AppearanceMode) => void;
  /** Toggle between light/dark (falls back to system-aware default). */
  toggleAppearance: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function systemMode(system: ColorSchemeName): ThemeMode {
  return system === 'dark' ? 'dark' : 'light';
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const system = useColorScheme();
  const [appearance, setAppearanceState] = useState<AppearanceMode>('system');

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((value) => {
        if (value === 'light' || value === 'dark' || value === 'system') {
          setAppearanceState(value);
        }
      })
      .catch(() => {
        // Non-fatal: default to system appearance.
      });
  }, []);

  const setAppearance = useCallback((mode: AppearanceMode) => {
    setAppearanceState(mode);
    AsyncStorage.setItem(STORAGE_KEY, mode).catch(() => {
      // Non-fatal: persistence failure only loses the preference.
    });
  }, []);

  const toggleAppearance = useCallback(() => {
    setAppearanceState((current) => {
      const next: AppearanceMode = current === 'system'
        ? system === 'dark'
          ? 'light'
          : 'dark'
        : current === 'light'
          ? 'dark'
          : 'light';
      AsyncStorage.setItem(STORAGE_KEY, next).catch(() => {
        // Non-fatal.
      });
      return next;
    });
  }, [system]);

  const mode: ThemeMode = appearance === 'system' ? systemMode(system) : appearance;
  const theme = useMemo(() => makeTheme(mode), [mode]);
  const value = useMemo<ThemeContextValue>(
    () => ({ theme, appearance, setAppearance, toggleAppearance }),
    [theme, appearance, setAppearance, toggleAppearance],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (value === null) {
    throw new Error('useTheme must be used within a <ThemeProvider>.');
  }
  return value;
}