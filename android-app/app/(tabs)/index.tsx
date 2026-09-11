import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';

import { Chip } from '@/components/Chip';
import { GlassSheet } from '@/components/GlassSheet';
import { Icon } from '@/components/Icon';
import { IconButton } from '@/components/IconButton';
import { MapCanvas } from '@/components/MapCanvas';
import { PulseMarker } from '@/components/MapAnnotations';
import { ModeTabs } from '@/components/ModeTabs';
import { Screen } from '@/components/Screen';
import { SearchBar } from '@/components/SearchBar';
import { fonts, radius, spacing } from '@/constants/theme';
import { homeCategories, recentDestinations, routeModes } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';
import { greeting } from '@/utils/format';
import { useState } from 'react';

export default function ExploreScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const [mode, setMode] = useState('car');

  return (
    <Screen topInset={false} bottomInset={false} backgroundColor={theme.mode === 'dark' ? '#0a1120' : '#d6e2f0'}>
      <MapCanvas backdrop="aerial" />

      <View style={[styles.topBar, { paddingTop: insets.top + spacing.lg }]}>
        <View style={styles.topRow}>
          <View style={styles.searchWrap}>
            <SearchBar onPress={() => router.push('/search')} />
          </View>
          <View style={[styles.avatar, { backgroundColor: theme.colors.primaryContainer }]}>
            <Text style={[styles.avatarText, { color: theme.colors.onPrimaryContainer, fontFamily: fonts.bold }]}>A</Text>
          </View>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipsRow} style={styles.chipsScroll}>
          {homeCategories.map((cat) => (
            <Chip key={cat.id} icon={cat.icon} label={cat.label} onPress={() => {}} />
          ))}
        </ScrollView>
      </View>

      <View style={[styles.rightControls, { top: insets.top + 196 }]}>
        <IconButton name="compass" accessibilityLabel="Compass" />
        <IconButton name="layers" accessibilityLabel="Map layers" onPress={() => router.push('/map/layers')} />
        <IconButton name="recenter" accessibilityLabel="Recenter map" />
      </View>

      <View style={styles.centerMarker}>
        <PulseMarker size={28} />
      </View>

      <View style={[styles.bottomWrap, { bottom: insets.bottom + 72 }]}>
        <GlassSheet>
          <Text style={[styles.greeting, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>{greeting(new Date())}!</Text>
          <Text style={[styles.subtext, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Where would you like to go today?
          </Text>

          <View style={styles.modesRow}>
            <ModeTabs options={routeModes} value={mode} onChange={setMode} />
          </View>

          <View style={styles.recentHeader}>
            <Text style={[styles.recentTitle, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>Recent Destinations</Text>
          </View>

          {recentDestinations.map((place) => (
            <Pressable
              key={place.id}
              onPress={() => router.push({ pathname: '/place', params: { id: place.id } })}
              style={({ pressed }) => [styles.recentRow, pressed && { opacity: 0.7 }]}
            >
              <View style={[styles.recentIcon, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
                <Icon name="destination" size={18} color={theme.colors.primary} />
              </View>
              <View style={styles.recentText}>
                <Text numberOfLines={1} style={[styles.recentName, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>
                  {place.name}
                </Text>
                <Text numberOfLines={1} style={[styles.recentAddr, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                  {place.address}
                </Text>
              </View>
              <Icon name="forward" size={18} color={theme.colors.outline} />
            </Pressable>
          ))}
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
  },
  topRow: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  searchWrap: { flex: 1 },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontSize: 18 },
  chipsScroll: { marginTop: spacing.md },
  chipsRow: { gap: spacing.sm, paddingRight: spacing.xl },
  rightControls: {
    position: 'absolute',
    right: spacing.gutter,
    gap: spacing.sm,
    zIndex: 10,
  },
  centerMarker: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
  },
  greeting: { fontSize: 22, lineHeight: 28, marginTop: spacing.xs },
  subtext: { fontSize: 14, lineHeight: 19, marginTop: spacing.xs, marginBottom: spacing.md },
  modesRow: { marginLeft: -spacing.lg, marginRight: -spacing.lg },
  recentHeader: { marginTop: spacing.lg, marginBottom: spacing.sm },
  recentTitle: { fontSize: 15, lineHeight: 20 },
  recentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  recentIcon: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recentText: { flex: 1 },
  recentName: { fontSize: 14, lineHeight: 19 },
  recentAddr: { fontSize: 12, lineHeight: 16, marginTop: 1 },
});