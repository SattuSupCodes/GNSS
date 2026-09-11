/**
 * NavSphere design tokens.
 *
 * Derived from the Google Stitch "NavSphere – Dead Reckoning Navigation App"
 * export (`precision_aerospace_guidance/DESIGN.md` and the screen HTML sources).
 *
 * The system follows an aerospace-grade geospatial visual language:
 *   - Calibrated restraint (surfaces recede, map dominates)
 *   - Atmospheric depth (layered frosted-glass panels with hairline rims)
 *   - Tactical clarity (deterministic status chromas, Inter typography)
 */

export type ThemeMode = 'light' | 'dark';
export type AppearanceMode = 'system' | 'light' | 'dark';

/** Brand & status chromas (from the Stitch design system). */
export const palette = {
  electricAzure: '#0A66C2',
  electricCyan: '#00C4FD',
  navSatAzure: '#0284C7',
  obsidian: '#0B0F17',
  nominal: '#10B981',
  degraded: '#F59E0B',
  critical: '#EF4444',
  mutedSlate: '#94A3B8',
  white: '#FFFFFF',
  black: '#000000',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  gutter: 16,
  margin: 16,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  full: 9999,
} as const;

export const fonts = {
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semibold: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
  extrabold: 'Inter_800ExtraBold',
  black: 'Inter_900Black',
} as const;

/** Translucent surface used for the "glass" treatment. */
export interface GlassSpec {
  /** Base fill color (already translucent). */
  fill: string;
  /** 1px hairline rim color. */
  border: string;
  /** Interior top highlight color (inset hairline). */
  highlight: string;
  /** Backdrop blur intensity (0 on platforms without blur support). */
  blur: number;
}

export interface ThemeColors {
  background: string;
  surface: string;
  surfaceContainerLowest: string;
  surfaceContainerLow: string;
  surfaceContainer: string;
  surfaceContainerHigh: string;
  surfaceContainerHighest: string;
  surfaceBright: string;
  onSurface: string;
  onSurfaceVariant: string;
  primary: string;
  onPrimary: string;
  primaryContainer: string;
  onPrimaryContainer: string;
  secondary: string;
  onSecondary: string;
  secondaryContainer: string;
  onSecondaryContainer: string;
  error: string;
  onError: string;
  errorContainer: string;
  onErrorContainer: string;
  success: string;
  warning: string;
  critical: string;
  outline: string;
  outlineVariant: string;
  hairline: string;
  glassFloating: GlassSpec;
  glassTactical: GlassSpec;
  glassSheet: GlassSpec;
}

export interface Theme {
  mode: ThemeMode;
  colors: ThemeColors;
}

const darkColors: ThemeColors = {
  background: '#0f131c',
  surface: '#0f131c',
  surfaceContainerLowest: '#0a0e16',
  surfaceContainerLow: '#181c24',
  surfaceContainer: '#1c2028',
  surfaceContainerHigh: '#262a33',
  surfaceContainerHighest: '#31353e',
  surfaceBright: '#353942',
  onSurface: '#dfe2ee',
  onSurfaceVariant: '#c1c6d4',
  primary: '#a8c8ff',
  onPrimary: '#003062',
  primaryContainer: '#0a66c2',
  onPrimaryContainer: '#dbe6ff',
  secondary: '#92dbff',
  onSecondary: '#003547',
  secondaryContainer: '#00c4fd',
  onSecondaryContainer: '#004d66',
  error: '#ffb4ab',
  onError: '#690005',
  errorContainer: '#93000a',
  onErrorContainer: '#ffdad6',
  success: '#10B981',
  warning: '#F59E0B',
  critical: '#EF4444',
  outline: '#8b919e',
  outlineVariant: '#414752',
  hairline: 'rgba(255,255,255,0.10)',
  glassFloating: {
    fill: 'rgba(11,15,23,0.72)',
    border: 'rgba(255,255,255,0.12)',
    highlight: 'rgba(255,255,255,0.15)',
    blur: 20,
  },
  glassTactical: {
    fill: 'rgba(11,15,23,0.90)',
    border: 'rgba(255,255,255,0.10)',
    highlight: 'rgba(255,255,255,0.15)',
    blur: 24,
  },
  glassSheet: {
    fill: 'rgba(18,22,30,0.94)',
    border: 'rgba(255,255,255,0.08)',
    highlight: 'rgba(255,255,255,0.10)',
    blur: 24,
  },
};

const lightColors: ThemeColors = {
  background: '#eef1f6',
  surface: '#f6f8fb',
  surfaceContainerLowest: '#ffffff',
  surfaceContainerLow: '#f8fafc',
  surfaceContainer: '#eef1f6',
  surfaceContainerHigh: '#e3e8f0',
  surfaceContainerHighest: '#d9e0ea',
  surfaceBright: '#ffffff',
  onSurface: '#0f172a',
  onSurfaceVariant: '#475569',
  primary: '#0a66c2',
  onPrimary: '#ffffff',
  primaryContainer: '#d6e3ff',
  onPrimaryContainer: '#0c3567',
  secondary: '#00648c',
  onSecondary: '#ffffff',
  secondaryContainer: '#bfe9ff',
  onSecondaryContainer: '#0a3f54',
  error: '#d92d20',
  onError: '#ffffff',
  errorContainer: '#ffdad6',
  onErrorContainer: '#7f1d1d',
  success: '#059669',
  warning: '#d97706',
  critical: '#dc2626',
  outline: '#64748b',
  outlineVariant: '#cbd5e1',
  hairline: 'rgba(15,23,42,0.08)',
  glassFloating: {
    fill: 'rgba(248,250,252,0.84)',
    border: 'rgba(15,23,42,0.10)',
    highlight: 'rgba(255,255,255,0.9)',
    blur: 20,
  },
  glassTactical: {
    fill: 'rgba(248,250,252,0.92)',
    border: 'rgba(15,23,42,0.08)',
    highlight: 'rgba(255,255,255,1)',
    blur: 24,
  },
  glassSheet: {
    fill: 'rgba(252,253,255,0.96)',
    border: 'rgba(15,23,42,0.06)',
    highlight: 'rgba(255,255,255,1)',
    blur: 24,
  },
};

export function makeTheme(mode: ThemeMode): Theme {
  return { mode, colors: mode === 'dark' ? darkColors : lightColors };
}

/** Convert a hex color to an rgba string with the given alpha. */
export function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace('#', '');
  const full = value.length === 3 ? value.split('').map((c) => c + c).join('') : value;
  const int = parseInt(full, 16);
  const r = (int >> 16) & 255;
  const g = (int >> 8) & 255;
  const b = int & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}