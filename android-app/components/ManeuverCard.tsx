import { StyleSheet, Text, View } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { Icon, type IconName } from '@/components/Icon';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface LaneSpec {
  total: number;
  active: number;
  direction?: 'left' | 'right';
}

interface ManeuverCardProps {
  icon: IconName;
  instruction: string;
  distance?: string;
  lanes?: LaneSpec;
  next?: { icon: IconName; label: string; distance: string };
}

export function ManeuverCard({ icon, instruction, distance, lanes, next }: ManeuverCardProps) {
  const { theme } = useTheme();

  return (
    <GlassSurface variant="tactical" style={styles.card}>
      <View style={styles.row}>
        <View style={[styles.iconBubble, { backgroundColor: theme.colors.primaryContainer }]}>
          <Icon name={icon} size={26} color={theme.colors.onPrimaryContainer} />
        </View>
        <View style={styles.instructionWrap}>
          <Text style={[styles.instruction, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
            {instruction}
          </Text>
        </View>
        {distance ? (
          <Text style={[styles.distance, { color: theme.colors.primary, fontFamily: fonts.extrabold }]}>{distance}</Text>
        ) : null}
      </View>

      {lanes ? <Lanes spec={lanes} /> : null}

      {next ? (
        <View style={[styles.nextRow, { borderTopColor: theme.colors.glassTactical.border }]}>
          <Icon name={next.icon} size={16} color={theme.colors.onSurfaceVariant} />
          <Text style={[styles.nextLabel, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            {next.label}
          </Text>
          <Text style={[styles.nextDistance, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>{next.distance}</Text>
        </View>
      ) : null}
    </GlassSurface>
  );
}

function Lanes({ spec }: { spec: LaneSpec }) {
  const { theme } = useTheme();
  const activeFrom = spec.direction === 'right' ? spec.total - spec.active : 0;
  const items = Array.from({ length: spec.total });

  return (
    <View style={styles.lanesRow}>
      {items.map((_, index) => {
        const active = index >= activeFrom && index < activeFrom + spec.active;
        return (
          <View
            key={index}
            style={[
              styles.lane,
              {
                backgroundColor: active ? theme.colors.primary : 'transparent',
                borderColor: active ? theme.colors.primary : theme.colors.outlineVariant,
              },
            ]}
          >
            {active && spec.direction !== undefined ? (
              <Icon name={spec.direction === 'right' ? 'turnRight' : 'turnLeft'} size={16} color={theme.colors.onPrimary} />
            ) : (
              <Icon name="straight" size={16} color={theme.colors.outline} />
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: radius.xl,
    padding: spacing.lg,
    gap: spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  iconBubble: {
    width: 52,
    height: 52,
    borderRadius: radius.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  instructionWrap: {
    flex: 1,
  },
  instruction: {
    fontSize: 16,
    lineHeight: 21,
  },
  distance: {
    fontSize: 22,
    lineHeight: 26,
  },
  lanesRow: {
    flexDirection: 'row',
    gap: spacing.xs,
  },
  lane: {
    flex: 1,
    height: 42,
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 2,
  },
  nextRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingTop: spacing.md,
  },
  nextLabel: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
  },
  nextDistance: {
    fontSize: 13,
    lineHeight: 18,
  },
});