import { StyleSheet, Text, View } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Polygon, Stop } from 'react-native-svg';

import { fonts } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface NavSphereLogoProps {
  size?: number;
}

export function NavSphereLogo({ size = 44 }: NavSphereLogoProps) {
  const r = size / 2;
  const cx = r;
  const cy = r;
  const diamond = `${cx},${cy - r * 0.55} ${cx + r * 0.55},${cy} ${cx},${cy + r * 0.55} ${cx - r * 0.55},${cy}`;

  return (
    <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <Defs>
        <LinearGradient id="navsphere-mark" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor="#00E5FF" />
          <Stop offset="0.45" stopColor="#0A66C2" />
          <Stop offset="1" stopColor="#023E8A" />
        </LinearGradient>
      </Defs>
      <Circle cx={cx} cy={cy} r={r - 1} fill="none" stroke="url(#navsphere-mark)" strokeWidth={2} />
      <Polygon points={diamond} fill="url(#navsphere-mark)" />
    </Svg>
  );
}

interface WordmarkProps {
  size?: 'small' | 'regular';
}

export function NavSphereWordmark({ size = 'regular' }: WordmarkProps) {
  const { theme } = useTheme();
  const fontSize = size === 'small' ? 14 : 18;

  return (
    <View style={styles.wordmark}>
      <Text style={[styles.word, { color: theme.colors.onSurface, fontFamily: fonts.black, fontSize }]}>
        NAVS{'\u200B'}PHERE
      </Text>
      <Text
        style={[
          styles.badge,
          { color: theme.colors.secondary, fontFamily: fonts.bold, fontSize: size === 'small' ? 9 : 10 },
        ]}
      >
        IDR
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wordmark: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  word: {
    letterSpacing: 1.2,
  },
  badge: {
    marginLeft: 4,
    letterSpacing: 1,
  },
});