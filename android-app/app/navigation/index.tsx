import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { GlassSheet } from '@/components/GlassSheet';
import { IconButton } from '@/components/IconButton';
import { ManeuverCard } from '@/components/ManeuverCard';
import { NavMap } from '@/components/maps/NavMap';
import { NavSphereLogo } from '@/components/NavSphereLogo';
import { PrimaryButton, SecondaryButton } from '@/components/Buttons';
import { Screen } from '@/components/Screen';
import { SpeedBadge } from '@/components/SpeedBadge';
import { StatusBanner } from '@/components/StatusBanner';
import { fonts, radius, spacing } from '@/constants/theme';
import { formatEtaTime, formatRemainingDuration } from '@/core/eta';
import { useTheme } from '@/lib/theme';
import { useNavigationSession } from '@/state/NavigationProvider';
import { formatMeters, formatSpeedKmh } from '@/utils/format';
import { iconForAction } from '@/utils/maneuver';

const PHASE_LABEL: Record<string, string> = {
  starting: 'Confirming position',
  navigating: 'Navigating',
  degraded: 'Reduced accuracy',
  lost: 'Signal lost',
  recovering: 'Recovering signal',
  rerouting: 'Rerouting',
  arrived: 'Arrived',
};

export default function NavigationScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const { snapshot, actions, demoMode, settings } = useNavigationSession();
  const [followUser, setFollowUser] = useState(true);

  const route = snapshot.route;
  const progress = snapshot.progress;
  const maneuver = progress?.nextManeuver ?? null;
  const nextAfter = maneuver && progress?.remainingManeuvers ? progress.remainingManeuvers[1] ?? null : null;
  const status = snapshot.positioningStatus;
  const prominentStatus = status !== 'available' || snapshot.phase === 'rerouting';

  function endNavigation() {
    actions.cancelNavigation();
    router.replace('/');
  }

  return (
    <Screen topInset={false} bottomInset={false}>
      <NavMap
        styleId={settings.map.styleId}
        coords={route?.geometry ?? null}
        origin={null}
        destination={snapshot.destination}
        userPosition={snapshot.position}
        followUser={followUser}
        onUserInteraction={() => setFollowUser(false)}
      />

      <View style={[styles.topBar, { paddingTop: insets.top + spacing.md }]}>
        <View style={styles.brandPill}>
          <NavSphereLogo size={30} />
        </View>
        <View style={styles.titleWrap}>
          <Text style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>
            Turn-by-Turn Guidance
          </Text>
          <Text numberOfLines={1} style={[styles.destination, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            {demoMode ? 'Demo drive · simulated position' : snapshot.destination ? `${snapshot.destination.latitude.toFixed(5)}, ${snapshot.destination.longitude.toFixed(5)}` : ''}
          </Text>
        </View>
        <IconButton name="mute" accessibilityLabel="Mute guidance" />
      </View>

      {prominentStatus ? (
        <View style={[styles.bannerWrap, { top: insets.top + 96 }]}>
          <StatusBanner status={status} prominent />
        </View>
      ) : null}

      {snapshot.phase !== 'arrived' ? (
        <View style={[styles.maneuverWrap, { top: insets.top + (prominentStatus ? 190 : 146) }]}>
          {maneuver ? (
            <ManeuverCard
              icon={iconForAction(maneuver.action)}
              instruction={maneuver.instruction}
              distance={formatMeters(progress?.distanceToNextManeuverMeters ?? maneuver.approachDistanceMeters)}
              next={nextAfter ? { icon: iconForAction(nextAfter.action), label: nextAfter.instruction, distance: formatMeters(nextAfter.approachDistanceMeters) } : undefined}
            />
          ) : (
            <ManeuverCard icon="straight" instruction="Proceeding to destination" next={undefined} />
          )}
        </View>
      ) : null}

      {snapshot.phase === 'arrived' ? (
        <View style={[styles.arrivedWrap, { top: insets.top + 146 }]}>
          <GlassSheet style={styles.arrivedCard}>
            <Text style={[styles.arrivedTitle, { color: theme.colors.success, fontFamily: fonts.bold }]}>
              You’ve arrived
            </Text>
            <Text style={[styles.arrivedSub, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
              Destination reached. Safe travels.
            </Text>
          </GlassSheet>
        </View>
      ) : null}

      <View style={[styles.rightControls, { top: insets.top + 190 }]}>
        <IconButton name="recenter" accessibilityLabel="Recenter map" onPress={() => setFollowUser(true)} />
      </View>

      <View style={[styles.speedBadge, { top: insets.top + 320 }]}>
        <SpeedBadge value={formatSpeedKmh(snapshot.speedMps)} limit="—" />
      </View>

      <View style={[styles.bottomWrap, { bottom: insets.bottom + spacing.md }]}>
        <GlassSheet>
          <View style={styles.etaRow}>
            <View>
              <Text style={[styles.eta, { color: theme.colors.primary, fontFamily: fonts.extrabold }]}>
                {formatEtaTime(snapshot.etaMillis)}
              </Text>
              <Text style={[styles.etaMeta, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
                {`${progress ? formatRemainingDuration(progress.remainingDurationSeconds) : '--'} \u00b7 ${progress ? formatMeters(progress.remainingDistanceMeters) : '--'}`}
              </Text>
            </View>
            <View style={[styles.smoothPill, { backgroundColor: theme.colors.secondaryContainer }]}>
              <Text style={[styles.smoothText, { color: theme.colors.onSecondaryContainer, fontFamily: fonts.semibold }]}>
                {PHASE_LABEL[snapshot.phase] ?? 'Navigation'}
              </Text>
            </View>
          </View>

          {snapshot.rerouting ? (
            <Text style={[styles.rerouteNote, { color: theme.colors.warning, fontFamily: fonts.medium }]}>
              Finding a better route…
            </Text>
          ) : null}

          <View style={styles.actions}>
            <SecondaryButton icon="list" onPress={() => router.back()}>
              Overview
            </SecondaryButton>
            <View style={{ flex: 1 }}>
              <PrimaryButton icon="gpsOff" style={{ backgroundColor: theme.colors.error }} onPress={endNavigation}>
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
  arrivedWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
  },
  arrivedCard: { paddingHorizontal: spacing.lg, paddingTop: spacing.lg, paddingBottom: spacing.lg },
  arrivedTitle: { fontSize: 20, lineHeight: 26 },
  arrivedSub: { fontSize: 13, lineHeight: 18, marginTop: 2 },
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
  rerouteNote: {
    fontSize: 13,
    lineHeight: 18,
    marginBottom: spacing.md,
  },
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
  },
});