import type { PropsWithChildren } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, {
  Circle,
  Defs,
  Line,
  LinearGradient,
  Path,
  Pattern,
  RadialGradient,
  Rect,
  Stop,
} from 'react-native-svg';

import { useTheme } from '@/lib/theme';

export type MapBackdrop = 'aerial' | 'route' | 'tunnel';

interface MapCanvasProps extends PropsWithChildren {
  backdrop?: MapBackdrop;
  style?: StyleProp<ViewStyle>;
}

/**
 * Map placeholder boundary.
 *
 * Renders an abstract stylised backdrop (grid, gradient, tunnel motif) only.
 * A real MapLibre / vector map will replace this layer — no fake map imagery
 * is ever drawn here.
 */
export function MapCanvas({ backdrop = 'aerial', style, children }: MapCanvasProps) {
  const { theme } = useTheme();
  const dark = theme.mode === 'dark';

  const top = dark ? '#0a1120' : '#d6e2f0';
  const bottom = dark ? '#0b0f17' : '#e6edf6';
  const grid = dark ? '#ffffff' : '#0f172a';
  const glow = dark ? '#00c4fd' : '#0a66c2';
  const vignette = dark ? '#0b0f17' : '#dfe7f1';

  return (
    <View style={[styles.canvas, style]} pointerEvents="box-none">
      <Svg width="100%" height="100%" style={StyleSheet.absoluteFill}>
        <Defs>
          <LinearGradient id="map-bg" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={top} />
            <Stop offset="1" stopColor={bottom} />
          </LinearGradient>
          <RadialGradient id="map-glow" cx="0.5" cy="0.45" r="0.6">
            <Stop offset="0" stopColor={glow} stopOpacity={dark ? 0.22 : 0.12} />
            <Stop offset="1" stopColor={glow} stopOpacity={0} />
          </RadialGradient>
          {backdrop === 'tunnel' ? (
            <RadialGradient id="tunnel-fade" cx="0.5" cy="0.42" r="0.75">
              <Stop offset="0" stopColor="#000000" stopOpacity={0.05} />
              <Stop offset="0.7" stopColor="#000000" stopOpacity={0.55} />
              <Stop offset="1" stopColor="#000000" stopOpacity={0.85} />
            </RadialGradient>
          ) : null}
        </Defs>

        <Rect width="100%" height="100%" fill="url(#map-bg)" />
        <Rect width="100%" height="100%" fill="url(#map-glow)" />

        {backdrop !== 'tunnel' ? (
          <Svg width="100%" height="100%" style={StyleSheet.absoluteFill}>
            <Defs>
              <Pattern id="map-grid" width={40} height={40} patternUnits="userSpaceOnUse">
                <Line x1={40} y1={0} x2={40} y2={40} stroke={grid} strokeOpacity={dark ? 0.05 : 0.06} />
                <Line x1={0} y1={40} x2={40} y2={40} stroke={grid} strokeOpacity={dark ? 0.05 : 0.06} />
                <Circle cx={40} cy={40} r={1.2} fill={grid} fillOpacity={dark ? 0.12 : 0.1} />
              </Pattern>
            </Defs>
            <Rect width="100%" height="100%" fill="url(#map-grid)" />
          </Svg>
        ) : (
          <Svg width="100%" height="100%" style={StyleSheet.absoluteFill}>
            {[0.18, 0.34, 0.5, 0.66, 0.82].map((f) => (
              <Circle
                key={f}
                cx="50%"
                cy="42%"
                r={`${f * 100}%`}
                fill="none"
                stroke={dark ? '#00c4fd' : '#0a66c2'}
                strokeOpacity={0.08}
              />
            ))}
            <Path
              d="M 220 560 C 160 480, 240 300, 420 180"
              fill="none"
              stroke={dark ? '#00c4fd' : '#0a66c2'}
              strokeOpacity={0.25}
              strokeWidth={3}
            />
            <Rect width="100%" height="100%" fill="url(#tunnel-fade)" />
          </Svg>
        )}

        <Rect width="100%" height="100%" fill={vignette} opacity={dark ? 0.45 : 0.25} />
      </Svg>

      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  canvas: {
    flex: 1,
    overflow: 'hidden',
  },
});