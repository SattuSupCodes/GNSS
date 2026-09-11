import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { ScreenHeader } from '@/components/Header';
import { Icon } from '@/components/Icon';
import { Pressable } from 'react-native';
import { Screen } from '@/components/Screen';
import { SettingsGroup, ToggleRow, SectionHeader } from '@/components/SettingsBits';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { useNavigationSession } from '@/state/NavigationProvider';

function Stepper({ label, value, unit, min, max, step, onChange }: { label: string; value: number; unit: string; min: number; max: number; step: number; onChange: (next: number) => void }) {
  const { theme } = useTheme();

  function clamp(next: number) {
    return Math.max(min, Math.min(max, next));
  }

  return (
    <View style={styles.stepperRow}>
      <Text style={[styles.stepperLabel, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>{label}</Text>
      <View style={styles.stepperControls}>
        <Pressable
          onPress={() => onChange(clamp(value - step))}
          accessibilityRole="button"
          accessibilityLabel={`Decrease ${label}`}
          style={({ pressed }) => [styles.stepBtn, { backgroundColor: theme.colors.surfaceContainerHigh }, pressed && { opacity: 0.7 }]}
        >
          <Icon name="minus" size={16} color={theme.colors.onSurface} />
        </Pressable>
        <Text style={[styles.stepperValue, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
          {value} <Text style={[styles.stepperUnit, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>{unit}</Text>
        </Text>
        <Pressable
          onPress={() => onChange(clamp(value + step))}
          accessibilityRole="button"
          accessibilityLabel={`Increase ${label}`}
          style={({ pressed }) => [styles.stepBtn, { backgroundColor: theme.colors.surfaceContainerHigh }, pressed && { opacity: 0.7 }]}
        >
          <Icon name="plus" size={16} color={theme.colors.onSurface} />
        </Pressable>
      </View>
    </View>
  );
}

export default function NavigationSettingsScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { settings, actions } = useNavigationSession();
  const nav = settings.navigation;

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View>
          <ScreenHeader title="Navigation" onBack={() => router.back()} variant="plain" />
        </View>

        <Text style={[styles.note, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Rerouting recomputes the route when you drift more than the threshold off the line.
        </Text>

        <SectionHeader title="Rerouting" />
        <SettingsGroup>
          <ToggleRow
            icon="route"
            title="Automatic rerouting"
            subtitle="Recompute the route when off-course"
            value={nav.rerouteEnabled}
            onValueChange={(value) => actions.updateSettings({ navigation: { ...nav, rerouteEnabled: value } })}
          />
        </SettingsGroup>

        {nav.rerouteEnabled ? (
          <>
            <SectionHeader title="Thresholds" />
            <View style={[styles.thresholds, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }]}>
              <Stepper
                label="Off-route threshold"
                value={nav.rerouteThresholdMeters}
                unit="m"
                min={10}
                max={200}
                step={10}
                onChange={(rerouteThresholdMeters) => actions.updateSettings({ navigation: { ...nav, rerouteThresholdMeters } })}
              />
              <Stepper
                label="Reroute cooldown"
                value={nav.rerouteCooldownSeconds}
                unit="s"
                min={5}
                max={120}
                step={5}
                onChange={(rerouteCooldownSeconds) => actions.updateSettings({ navigation: { ...nav, rerouteCooldownSeconds } })}
              />
              <Stepper
                label="Arrival distance"
                value={nav.arrivalThresholdMeters}
                unit="m"
                min={5}
                max={100}
                step={5}
                onChange={(arrivalThresholdMeters) => actions.updateSettings({ navigation: { ...nav, arrivalThresholdMeters } })}
              />
            </View>
          </>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingBottom: spacing.xl,
  },
  note: {
    fontSize: 13,
    lineHeight: 18,
    paddingHorizontal: spacing.gutter,
    marginTop: spacing.sm,
  },
  thresholds: {
    marginHorizontal: spacing.gutter,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
  stepperRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.md,
  },
  stepperLabel: { fontSize: 14, lineHeight: 19, flex: 1 },
  stepperControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  stepBtn: {
    width: 32,
    height: 32,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepperValue: { fontSize: 14, lineHeight: 19, minWidth: 64, textAlign: 'center' },
  stepperUnit: { fontSize: 12, lineHeight: 19 },
});