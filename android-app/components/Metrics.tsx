import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { Icon, type IconName } from '@/components/Icon';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

export type MetricTone = 'ok' | 'warn' | 'idle' | 'demo';

interface MetricCardProps {
  label: string;
  value: string;
  unit?: string;
  tone?: MetricTone;
  icon?: IconName;
  style?: StyleProp<ViewStyle>;
}

export function MetricCard({ label, value, unit, tone = 'idle', icon, style }: MetricCardProps) {
  const { theme } = useTheme();
  const accent = tone === 'ok' ? theme.colors.success : tone === 'warn' ? theme.colors.warning : tone === 'demo' ? theme.colors.secondary : theme.colors.onSurfaceVariant;

  return (
    <GlassSurface variant="floating" style={[styles.card, style]}>
      <View style={styles.topRow}>
        {icon ? <Icon name={icon} size={16} color={accent} /> : null}
        <Text numberOfLines={1} style={[styles.label, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          {label}
        </Text>
      </View>
      <View style={styles.valueRow}>
        <Text style={[styles.value, { color: theme.colors.onSurface, fontFamily: fonts.extrabold }]}>{value}</Text>
        {unit ? <Text style={[styles.unit, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>{unit}</Text> : null}
      </View>
    </GlassSurface>
  );
}

interface TelemetryChipProps {
  label: string;
  value: string;
  tone?: MetricTone;
}

export function TelemetryChip({ label, value, tone = 'idle' }: TelemetryChipProps) {
  const { theme } = useTheme();
  const accent = tone === 'ok' ? theme.colors.success : tone === 'warn' ? theme.colors.warning : tone === 'demo' ? theme.colors.secondary : theme.colors.onSurfaceVariant;

  return (
    <View style={[styles.chip, { backgroundColor: theme.colors.surfaceContainerHigh, borderColor: theme.colors.outlineVariant }]}>
      <View style={[styles.chipDot, { backgroundColor: accent }]} />
      <Text style={[styles.chipLabel, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>{label}</Text>
      <Text style={[styles.chipValue, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>{value}</Text>
    </View>
  );
}

interface SensorRowProps {
  icon: IconName;
  name: string;
  state: string;
  tone?: MetricTone;
}

export function SensorRow({ icon, name, state, tone = 'idle' }: SensorRowProps) {
  const { theme } = useTheme();
  const accent = tone === 'ok' ? theme.colors.success : tone === 'warn' ? theme.colors.warning : tone === 'demo' ? theme.colors.secondary : theme.colors.outline;

  return (
    <View style={styles.sensorRow}>
      <Icon name={icon} size={18} color={accent} />
      <Text style={[styles.sensorName, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>{name}</Text>
      <View style={[styles.sensorState, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
        <View style={[styles.chipDot, { backgroundColor: accent }]} />
        <Text style={[styles.sensorStateText, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>{state}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.lg,
    padding: spacing.md,
    gap: spacing.xs,
    flexBasis: '46%',
    flexGrow: 1,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  label: {
    flex: 1,
    fontSize: 11,
    lineHeight: 15,
    letterSpacing: 0.3,
    textTransform: 'uppercase',
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 3,
  },
  value: {
    fontSize: 22,
    lineHeight: 26,
  },
  unit: {
    fontSize: 12,
    lineHeight: 26,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    borderRadius: radius.full,
    borderWidth: 1,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  chipDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  chipLabel: {
    fontSize: 12,
    lineHeight: 16,
  },
  chipValue: {
    fontSize: 12,
    lineHeight: 16,
  },
  sensorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
  },
  sensorName: {
    flex: 1,
    fontSize: 14,
    lineHeight: 18,
  },
  sensorState: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    borderRadius: radius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
  },
  sensorStateText: {
    fontSize: 11,
    lineHeight: 15,
  },
});