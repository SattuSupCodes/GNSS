import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Polygon, Polyline } from 'react-native-svg';

import { Icon, type IconName } from '@/components/Icon';
import { fonts, radius } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface PulseMarkerProps {
  size?: number;
  color?: string;
}

export function PulseMarker({ size = 26, color }: PulseMarkerProps) {
  const { theme } = useTheme();
  const marker = color ?? theme.colors.secondary;
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(pulse, {
        toValue: 1,
        duration: 2800,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const outer = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 2.6] });
  const inner = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.8] });
  const ringOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.4, 0] });

  const Ring = ({ pulseScale, width }: { pulseScale: Animated.AnimatedInterpolation<number> | Animated.Value; width: number }) => (
    <Animated.View
      style={[
        styles.ring,
        {
          width: size,
          height: size,
          borderColor: marker,
          borderWidth: width,
          opacity: ringOpacity,
          transform: [{ scale: pulseScale }],
        },
      ]}
    />
  );

  return (
    <View style={styles.markerWrap}>
      <Ring pulseScale={outer} width={1.5} />
      <Ring pulseScale={inner} width={2.5} />
      <View
        style={[
          styles.core,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            backgroundColor: marker,
            borderColor: theme.colors.onPrimary,
          },
        ]}
      />
    </View>
  );
}

interface RouteLineProps {
  points: string;
  color?: string;
  width?: number;
}

export function RouteLine({ points, color, width = 4 }: RouteLineProps) {
  const { theme } = useTheme();
  const stroke = color ?? theme.colors.primary;
  return (
    <Svg width="100%" height="100%" style={StyleSheet.absoluteFill} pointerEvents="none">
      <Polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeOpacity={0.22}
        strokeWidth={width * 3}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={width}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

interface WaypointProps {
  icon?: IconName;
  label?: string;
  color?: string;
  size?: number;
}

export function Waypoint({ icon, label, color, size = 30 }: WaypointProps) {
  const { theme } = useTheme();
  const marker = color ?? theme.colors.primary;
  return (
    <View style={styles.waypoint}>
      <View
        style={[
          styles.waypointCircle,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            backgroundColor: marker,
            borderColor: theme.colors.onPrimary,
          },
        ]}
      >
        {icon ? <Icon name={icon} size={size * 0.55} color={theme.colors.onPrimary} /> : null}
      </View>
      {label ? (
        <View style={[styles.waypointLabel, { backgroundColor: theme.colors.glassTactical.fill }]}>
          <Text style={[styles.waypointText, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>{label}</Text>
        </View>
      ) : null}
    </View>
  );
}

interface NavConeProps {
  size?: number;
  color?: string;
  rotation?: number;
}

export function NavCone({ size = 64, color, rotation = 0 }: NavConeProps) {
  const { theme } = useTheme();
  const fill = color ?? theme.colors.secondary;
  const r = size / 2;
  const points = `${r},${r - r * 0.82} ${r + r * 0.6},${r + r * 0.62} ${r},${r + r * 0.2} ${r - r * 0.6},${r + r * 0.62}`;
  return (
    <Svg width={size} height={size} style={{ transform: [{ rotate: `${rotation}deg` }] }} pointerEvents="none">
      <Polygon points={points} fill={fill} stroke={theme.colors.onSecondary} strokeWidth={1.5} strokeLinejoin="round" />
    </Svg>
  );
}

const styles = StyleSheet.create({
  markerWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    width: 96,
    height: 96,
  },
  ring: {
    position: 'absolute',
    borderRadius: 9999,
  },
  core: {
    borderWidth: 3,
  },
  waypoint: {
    alignItems: 'center',
  },
  waypointCircle: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
  },
  waypointLabel: {
    marginTop: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  waypointText: {
    fontSize: 11,
    letterSpacing: 0.5,
  },
});