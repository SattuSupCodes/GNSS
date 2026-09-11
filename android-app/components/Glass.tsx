import { BlurView } from 'expo-blur';
import type { PropsWithChildren } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import type { GlassSpec, ThemeColors } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

export type GlassVariant = 'floating' | 'tactical' | 'sheet';

interface GlassSurfaceProps extends PropsWithChildren {
  variant?: GlassVariant;
  style?: StyleProp<ViewStyle>;
  /** Toggle the backdrop blur (iOS real blur; Android translucent fallback). */
  blurred?: boolean;
}

const SPEC_KEY: Record<GlassVariant, keyof ThemeColors> = {
  floating: 'glassFloating',
  tactical: 'glassTactical',
  sheet: 'glassSheet',
};

export function GlassSurface({ variant = 'floating', style, children, blurred = true }: GlassSurfaceProps) {
  const { theme } = useTheme();
  const spec: GlassSpec = theme.colors[SPEC_KEY[variant]] as GlassSpec;
  const tint = theme.mode === 'dark' ? 'dark' : 'light';

  return (
    <BlurView
      intensity={blurred ? spec.blur : 0}
      tint={tint}
      style={[
        styles.base,
        { backgroundColor: spec.fill, borderColor: spec.border },
        style,
      ]}
    >
      {children}
      <View pointerEvents="none" style={[styles.highlight, { backgroundColor: spec.highlight }]} />
    </BlurView>
  );
}

const styles = StyleSheet.create({
  base: {
    borderWidth: StyleSheet.hairlineWidth,
    overflow: 'hidden',
  },
  highlight: {
    position: 'absolute',
    top: 0,
    left: 8,
    right: 8,
    height: 1,
    opacity: 0.5,
  },
});