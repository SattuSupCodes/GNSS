import { StyleSheet, Text, View } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface SpeedBadgeProps {
  /** Placeholder until a real GNSS provider reports speed. Never fabricates. */
  value?: string;
  limit?: string;
}

export function SpeedBadge({ value = '—', limit = '—' }: SpeedBadgeProps) {
  const { theme } = useTheme();

  return (
    <GlassSurface variant="tactical" style={styles.badge}>
      <Text style={[styles.label, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
        Speed
      </Text>
      <View style={styles.valueRow}>
        <Text style={[styles.value, { color: theme.colors.onSurface, fontFamily: fonts.extrabold }]}>{value}</Text>
        <Text style={[styles.unit, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>km/h</Text>
      </View>
      <Text style={[styles.limit, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
        Limit {limit}
      </Text>
    </GlassSurface>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: radius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    alignItems: 'center',
    minWidth: 92,
  },
  label: {
    fontSize: 11,
    lineHeight: 15,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 2,
  },
  value: {
    fontSize: 26,
    lineHeight: 30,
  },
  unit: {
    fontSize: 11,
    lineHeight: 30,
  },
  limit: {
    fontSize: 10,
    lineHeight: 14,
  },
});