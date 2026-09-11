import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PrimaryButton } from '@/components/Buttons';
import { Icon } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { ScreenHeader } from '@/components/Header';
import { fonts, radius, spacing } from '@/constants/theme';
import { demoRoute, routeSteps } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

export default function StepsScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();

  return (
    <Screen>
      <View style={styles.header}>
        <ScreenHeader
          title="Direction Steps"
          subtitle={`${demoRoute.destinationLabel} \u00b7 ${demoRoute.duration}`}
          onBack={() => router.back()}
        />
      </View>

      <ScrollView contentContainerStyle={styles.list}>
        <View style={[styles.routeSummary, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }]}>
          <Icon name="destination" size={16} color={theme.colors.primary} />
          <Text style={[styles.routeSummaryText, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
            {demoRoute.originLabel} → {demoRoute.destinationLabel}
          </Text>
        </View>

        {routeSteps.map((step, index) => {
          const last = index === routeSteps.length - 1;
          return (
            <View key={step.id} style={styles.stepRow}>
              <View style={styles.stepRail}>
                <View
                  style={[
                    styles.stepIconRing,
                    last
                      ? [styles.stepIconArrive, { backgroundColor: theme.colors.success }]
                      : { backgroundColor: theme.colors.primaryContainer },
                  ]}
                >
                  <Icon
                    name={step.icon}
                    size={18}
                    color={last ? theme.colors.onPrimary : theme.colors.onPrimaryContainer}
                  />
                </View>
                {!last ? <View style={[styles.rail, { backgroundColor: theme.colors.outlineVariant }]} /> : null}
              </View>
              <View style={styles.stepTextWrap}>
                <Text style={[styles.stepInstruction, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>
                  {step.instruction}
                </Text>
              </View>
              <Text style={[styles.stepDistance, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.semibold }]}>
                {step.distance}
              </Text>
            </View>
          );
        })}
      </ScrollView>

      <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
        <PrimaryButton icon="forward" onPress={() => router.push('/navigation/index')}>
          Start navigation
        </PrimaryButton>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingTop: spacing.md,
  },
  list: {
    paddingHorizontal: spacing.gutter,
    paddingTop: spacing.lg,
  },
  routeSummary: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    marginBottom: spacing.lg,
  },
  routeSummaryText: { flex: 1, fontSize: 13, lineHeight: 18 },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
  },
  stepRail: {
    alignItems: 'center',
    width: 38,
  },
  stepIconRing: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepIconArrive: {
    borderColor: 'transparent',
  },
  rail: {
    flex: 1,
    width: 2,
    marginVertical: spacing.xs,
  },
  stepTextWrap: {
    flex: 1,
    paddingTop: spacing.sm,
  },
  stepInstruction: { fontSize: 14, lineHeight: 19 },
  stepDistance: {
    fontSize: 13,
    lineHeight: 19,
    paddingTop: spacing.sm,
  },
  footer: {
    paddingHorizontal: spacing.gutter,
    paddingTop: spacing.sm,
  },
});