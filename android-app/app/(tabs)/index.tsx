import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';

import { Chip } from '@/components/Chip';
import { GlassSheet } from '@/components/GlassSheet';
import { Icon } from '@/components/Icon';
import { IconButton } from '@/components/IconButton';
import { NavMap } from '@/components/maps/NavMap';
import { SearchBar } from '@/components/SearchBar';
import { Screen } from '@/components/Screen';
import { StatusBanner } from '@/components/StatusBanner';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { loadRecentSearches } from '@/services/placesStore';
import { useNavigationSession } from '@/state/NavigationProvider';
import type { RecentSearch } from '@/types/places';
import { greeting } from '@/utils/format';

export default function ExploreScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const { snapshot, demoMode, settings } = useNavigationSession();
  const [recents, setRecents] = useState<RecentSearch[]>([]);

  const lost = snapshot.positioningStatus !== 'available';
  const userPosition = snapshot.position;

  useEffect(() => {
    loadRecentSearches().then(setRecents);
  }, []);

  return (
    <Screen topInset={false} bottomInset={false} backgroundColor={theme.mode === 'dark' ? '#0a1120' : '#d6e2f0'}>
      <NavMap
        styleId={settings.map.styleId}
        coords={null}
        origin={null}
        destination={null}
        userPosition={userPosition}
        followUser={settings.map.followUser}
        onUserInteraction={undefined}
      />

      <View style={[styles.topBar, { paddingTop: insets.top + spacing.lg }]}>
        <View style={styles.topRow}>
          <View style={styles.searchWrap}>
            <SearchBar onPress={() => router.push('/search')} />
          </View>
          <View style={[styles.avatar, { backgroundColor: theme.colors.primaryContainer }]}>
            <Text style={[styles.avatarText, { color: theme.colors.onPrimaryContainer, fontFamily: fonts.bold }]}>A</Text>
          </View>
        </View>

        {demoMode ? (
          <View style={styles.demoRow}>
            <Chip label="Demo mode · simulated position" icon="flask" selected />
          </View>
        ) : null}
      </View>

      <View style={[styles.rightControls, { top: insets.top + 196 }]}>
        <IconButton name="compass" accessibilityLabel="Compass" onPress={undefined} />
        <IconButton name="layers" accessibilityLabel="Map layers" onPress={() => router.push('/map/layers')} />
      </View>

      {lost ? (
        <View style={[styles.bannerWrap, { top: insets.top + (demoMode ? 150 : 168) }]}>
          <StatusBanner status={snapshot.positioningStatus} />
        </View>
      ) : null}

      <View style={[styles.bottomWrap, { bottom: insets.bottom + 72 }]}>
        <GlassSheet>
          <Text style={[styles.greeting, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>{greeting(new Date())}!</Text>
          <Text style={[styles.subtext, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Where would you like to go today?
          </Text>

          <View style={styles.recentHeader}>
            <Text style={[styles.recentTitle, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>Recent Searches</Text>
            {recents.length > 0 ? (
              <Pressable onPress={() => router.push('/search')} accessibilityRole="button">
                <Text style={[styles.recentAll, { color: theme.colors.primary, fontFamily: fonts.semibold }]}>See all</Text>
              </Pressable>
            ) : null}
          </View>

          {recents.slice(0, 3).map((place) => (
            <Pressable
              key={place.id}
              onPress={() => {
                router.push({
                  pathname: '/routing/preview',
                  params: {
                    lat: String(place.position?.latitude ?? ''),
                    lng: String(place.position?.longitude ?? ''),
                    name: place.name,
                    address: place.query || place.name,
                  },
                });
              }}
              style={({ pressed }) => [styles.recentRow, pressed && { opacity: 0.7 }]}
            >
              <View style={[styles.recentIcon, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
                <Icon name="history" size={18} color={theme.colors.primary} />
              </View>
              <View style={styles.recentText}>
                <Text numberOfLines={1} style={[styles.recentName, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>
                  {place.name}
                </Text>
                <Text numberOfLines={1} style={[styles.recentAddr, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                  {place.query || 'Saved location'}
                </Text>
              </View>
              <Icon name="forward" size={18} color={theme.colors.outline} />
            </Pressable>
          ))}

          {recents.length === 0 ? (
            <Text style={[styles.emptyRecents, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
              Search for a destination to see it here.
            </Text>
          ) : null}
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
  demoRow: {
    marginTop: spacing.sm,
    alignItems: 'flex-start',
  },
  rightControls: {
    position: 'absolute',
    right: spacing.gutter,
    gap: spacing.sm,
    zIndex: 10,
  },
  bannerWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
  },
  bottomWrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 10,
  },
  greeting: { fontSize: 22, lineHeight: 28, marginTop: spacing.xs },
  subtext: { fontSize: 14, lineHeight: 19, marginTop: spacing.xs, marginBottom: spacing.md },
  recentHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  recentTitle: { fontSize: 15, lineHeight: 20 },
  recentAll: { fontSize: 13, lineHeight: 18 },
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
  emptyRecents: {
    fontSize: 13,
    lineHeight: 18,
    paddingVertical: spacing.md,
    textAlign: 'center',
  },
});