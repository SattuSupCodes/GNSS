import { View, StyleSheet, Text } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { GlassSheet } from '@/components/GlassSheet';
import { IconButton } from '@/components/IconButton';
import { ManeuverCard } from '@/components/ManeuverCard';
import { MapCanvas } from '@/components/MapCanvas';
import { NavCone } from '@/components/MapAnnotations';
import { NavSphereLogo } from '@/components/NavSphereLogo';
import { PrimaryButton, SecondaryButton } from '@/components/Buttons';
import { Screen } from '@/components/Screen';
import { SpeedBadge } from '@/components/SpeedBadge';
import { StatusBanner } from '@/components/StatusBanner';
import { fonts, radius, spacing } from '@/constants/theme';
import { demoNavSession } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

export default function NavigationScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();

  return (
    <Screen topInset={false} bottomInset={false}>
      <MapCanvas backdrop="tunnel" />

      <View style={[styles.topBar, { paddingTop: insets.top + spacing.md }]}>
        <View style={styles.brandPill}>
          <NavSphereLogo size={30} />
        </View>
        <View style={styles.titleWrap}>
          <Text style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>
            Turn-by-Turn Guidance
          </Text>
          <Text
            numberOfLines={1}
            style={[styles.destination, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}
          >
            {demoNavSession.destinationLabel}
          </Text>
        </View>
        <IconButton name="mute" accessibilityLabel="Mute guidance" />
      </View>

      <View style={[styles.bannerWrap, { top: insets.top + 96 }]}>
        <StatusBanner status="gnss-lost" prominent />
      </View>

      <View style={[styles.maneuverWrap, { top: insets.top + 190 }]}>
        <ManeuverCard
          icon="turnRight"
          instruction={demoNavSession.currentInstruction}
          distance={demoNavSession.currentDistance}
          lanes={{ total: 4, active: 2, direction: 'right' }}
          next={demoNavSession.next}
        />
      </View>

      <View style={styles.centerCone} pointerEvents="none">
        <NavCone rotation={18} />
      </View>

      <View style={[styles.rightControls, { top: insets.top + 190 }]}>
        <IconButton name="recenter" accessibilityLabel="Recenter map" />
      </View>

      <View style={[styles.speedBadge, { top: insets.top + 320 }]}>
        <SpeedBadge value="—" limit="60" />
      </View>

      <View style={[styles.bottomWrap, { bottom: insets.bottom + spacing.md }]}>
        <GlassSheet>
          <View style={styles.etaRow}>
            <View>
              <Text style={[styles.eta, { color: theme.colors.primary, fontFamily: fonts.extrabold }]}>{demoNavSession.eta}</Text>
              <Text style={[styles.etaMeta, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
                {`${demoNavSession.durationRemaining} \u00b7 ${demoNavSession.distanceRemaining}`}
              </Text>
            </View>
            <View style={[styles.smoothPill, { backgroundColor: theme.colors.secondaryContainer }]}>
              <Text style={[styles.smoothText, { color: theme.colors.onSecondaryContainer, fontFamily: fonts.semibold }]}>
                {demoNavSession.smoothFlow}
              </Text>
            </View>
          </View>

          <View style={styles.actions}>
            <SecondaryButton icon="list" onPress={() => router.push('/routing/steps')}>
              Overview
            </SecondaryButton>
            <SecondaryButton icon="locationPin">Add Stop</SecondaryButton>
            <View style={{ flex: 1 }}>
              <PrimaryButton
                icon="gpsOff"
                style={{ backgroundColor: theme.colors.error }}
                onPress={() => router.replace('/')}
              >
                End
              </PrimaryButton>
            </View>
          </View>
        </GlassSheet>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topBar: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  brandPill: {
    padding: spacing.xs,
    borderRadius: radius.full,
    backgroundColor: 'transparent',
  },
  titleWrap: {
    flex: 1,
  },
  title: { fontSize: 17, lineHeight: 21 },
  destination: { fontSize: 12, lineHeight: 16, marginTop: 1 },
  bannerWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
  },
  maneuverWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
  },
  centerCone: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rightControls: {
    position: 'absolute',
    right: spacing.gutter,
    gap: spacing.sm,
    zIndex: 10,
  },
  speedBadge: {
    position: 'absolute',
    left: spacing.gutter,
    zIndex: 10,
  },
  bottomWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
  },
  etaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.lg,
  },
  eta: { fontSize: 30, lineHeight: 34 },
  etaMeta: { fontSize: 14, lineHeight: 19, marginTop: 2 },
  smoothPill: {
    borderRadius: radius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  smoothText: { fontSize: 13, lineHeight: 18 },
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
  },
});