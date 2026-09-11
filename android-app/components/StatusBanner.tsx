import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { friendlyPositionText } from '@/services/position';
import type { PositioningStatus } from '@/types/position';

interface StatusBannerProps {
  status?: PositioningStatus;
  /** Friendly override — never telemetry values. */
  message?: string;
  style?: StyleProp<ViewStyle>;
  prominent?: boolean;
}

const TONES: Record<PositioningStatus, 'success' | 'warning' | 'critical'> = {
  available: 'success',
  degraded: 'warning',
  lost: 'critical',
  recovering: 'warning',
};

const BLINK: Partial<Record<PositioningStatus, boolean>> = {
  lost: true,
  recovering: true,
};

export function StatusBanner({ status = 'available', message, style, prominent = false }: StatusBannerProps) {
  const { theme } = useTheme();
  const blink = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!BLINK[status]) {
      blink.setValue(1);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(blink, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(blink, { toValue: 0, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [status, blink]);

  const toneName = TONES[status];
  const tone = theme.colors[toneName];

  return (
    <GlassSurface variant="tactical" style={[styles.banner, prominent && styles.prominent, style]}>
      <View style={[styles.dotWrap, { borderColor: tone }]}>
        <Animated.View style={[styles.dot, { backgroundColor: tone, opacity: blink }]} />
      </View>
      <View style={styles.textWrap}>
        <Text style={[styles.message, prominent && styles.messageProminent, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
          {message ?? friendlyPositionText(status)}
        </Text>
      </View>
    </GlassSurface>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radius.lg,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
  },
  prominent: {
    borderRadius: radius.lg,
  },
  dotWrap: {
    width: 18,
    height: 18,
    borderRadius: 9999,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 9999,
  },
  textWrap: {
    flex: 1,
  },
  message: {
    fontSize: 13,
    lineHeight: 18,
  },
  messageProminent: {
    fontSize: 14,
    lineHeight: 19,
  },
});