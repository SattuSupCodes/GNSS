import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { PrimaryButton, SecondaryButton } from '@/components/Buttons';
import { Chip } from '@/components/Chip';
import { GlassSheet } from '@/components/GlassSheet';
import { Icon } from '@/components/Icon';
import { MapCanvas } from '@/components/MapCanvas';
import { RouteLine, Waypoint } from '@/components/MapAnnotations';
import { ModeTabs } from '@/components/ModeTabs';
import { Screen } from '@/components/Screen';
import { ScreenHeader } from '@/components/Header';
import { fonts, radius, spacing } from '@/constants/theme';
import { demoRoute, routeModes } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

const ROUTE_POINTS = '64,500 120,440 170,330 230,260 288,240 316,196';

export default function RoutePreviewScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const [mode, setMode] = useState(demoRoute.mode);

  return (
    <Screen topInset={false} bottomInset={false}>
      <MapCanvas backdrop="route" />

      <View style={styles.headerOverlay}>
        <ScreenHeader
          onBack={() => router.back()}
          title="Route Details"
          right={<Icon name="tune" size={20} />}
        />
      </View>

      <View style={styles.etaPill}>
        <Chip label={`ETA ${demoRoute.eta}`} icon="clock" />
      </View>

      <RouteLine points={ROUTE_POINTS} />

      <View style={styles.startMarker} pointerEvents="none">
        <Waypoint label="START" color={theme.colors.success} size={22} />
      </View>
      <View style={styles.destMarker} pointerEvents="none">
        <Waypoint icon="flight" color={theme.colors.primary} size={32} />
      </View>

      <View style={[styles.bottomWrap, { bottom: insets.bottom + spacing.md }]}>
        <GlassSheet>
          <View style={styles.summaryRow}>
            <View>
              <Text style={[styles.eta, { color: theme.colors.primary, fontFamily: fonts.extrabold }]}>{demoRoute.eta}</Text>
              <Text style={[styles.summaryMeta, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
                {`${demoRoute.duration} \u00b7 ${demoRoute.distanceKm}`}
              </Text>
            </View>
            <View style={[styles.fastestPill, { backgroundColor: theme.colors.secondaryContainer }]}>
              <Text style={[styles.fastestText, { color: theme.colors.onSecondaryContainer, fontFamily: fonts.semibold }]}>
                Fastest route
              </Text>
            </View>
          </View>

          <View style={styles.modesRow}>
            <ModeTabs options={routeModes} value={mode} onChange={setMode} />
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow}>
            <Chip icon="toll" label="Tolls possible" />
            <Chip icon="route" label={demoRoute.via} />
            <Chip icon="traffic" label="Light traffic" />
          </ScrollView>

          <View style={[styles.tipRow, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
            <Icon name="headsUp" size={18} color={theme.colors.secondary} />
            <Text style={[styles.tipText, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
              {demoRoute.tip}
            </Text>
          </View>

          <View style={styles.actions}>
            <SecondaryButton icon="list" onPress={() => router.push('/routing/steps')}>
              Steps
            </SecondaryButton>
            <PrimaryButton icon="forward" onPress={() => router.push('/navigation/index')}>
              Start
            </PrimaryButton>
          </View>
        </GlassSheet>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  headerOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
  etaPill: {
    position: 'absolute',
    top: 96,
    right: spacing.gutter,
  },
  startMarker: {
    position: 'absolute',
    left: 40,
    top: 460,
  },
  destMarker: {
    position: 'absolute',
    right: 56,
    top: 140,
  },
  bottomWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  eta: { fontSize: 30, lineHeight: 34 },
  summaryMeta: { fontSize: 14, lineHeight: 19, marginTop: 2 },
  fastestPill: {
    borderRadius: radius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  fastestText: { fontSize: 13, lineHeight: 18 },
  modesRow: { marginLeft: -spacing.lg, marginRight: -spacing.lg },
  chipsRow: { gap: spacing.sm, paddingTop: spacing.md, paddingRight: spacing.xl },
  tipRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginTop: spacing.lg,
  },
  tipText: { flex: 1, fontSize: 13, lineHeight: 18 },
  actions: {
    flexDirection: 'row',
    gap: spacing.md,
    marginTop: spacing.lg,
  },
});