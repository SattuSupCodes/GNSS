import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { Icon, type IconName } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { spacing, fonts, radius } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { deleteSavedPlace, loadSavedPlaces } from '@/services/placesStore';
import type { SavedPlace, SavedPlaceKind } from '@/types/places';

const KIND_ICON: Record<SavedPlaceKind, IconName> = {
  home: 'home',
  work: 'work',
  favorite: 'star',
};

export default function SavedScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const [places, setPlaces] = useState<SavedPlace[]>([]);

  const refresh = useCallback(() => {
    loadSavedPlaces().then(setPlaces);
  }, []);

  useEffect(refresh, [refresh]);

  function removePlace(id: string) {
    deleteSavedPlace(id).then(setPlaces).catch(() => {});
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>Saved Places</Text>
      </View>

      <ScrollView contentContainerStyle={styles.list}>
        {places.map((place) => (
          <Pressable
            key={place.id}
            onPress={() =>
              router.push({
                pathname: '/routing/preview',
                params: {
                  lat: String(place.position.latitude),
                  lng: String(place.position.longitude),
                  name: place.name,
                  address: place.address,
                },
              })
            }
            style={({ pressed }) => [styles.row, pressed && { opacity: 0.7 }]}
          >
            <View style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]}>
              <Icon name={KIND_ICON[place.kind]} size={20} color={theme.colors.onPrimaryContainer} />
            </View>
            <View style={styles.info}>
              <Text numberOfLines={1} style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>{place.name}</Text>
              <Text numberOfLines={1} style={[styles.address, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>{place.address}</Text>
            </View>
            <Pressable
              onPress={() => removePlace(place.id)}
              accessibilityRole="button"
              accessibilityLabel={`Remove ${place.name}`}
              hitSlop={12}
              style={({ pressed }) => [styles.remove, { backgroundColor: theme.colors.surfaceContainerHigh }, pressed && { opacity: 0.7 }]}
            >
              <Icon name="close" size={16} color={theme.colors.onSurfaceVariant} />
            </Pressable>
          </Pressable>
        ))}
      </ScrollView>

      {places.length === 0 ? (
        <GlassSurface style={styles.empty}>
          <Icon name="savedOutline" size={22} color={theme.colors.onSurfaceVariant} />
          <Text style={[styles.emptyText, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Nothing saved yet. Open a place and tap Save to keep it here.
          </Text>
        </GlassSurface>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.gutter,
    paddingTop: spacing.xl,
    paddingBottom: spacing.md,
  },
  title: { fontSize: 22, lineHeight: 28 },
  list: {
    paddingHorizontal: spacing.gutter,
    gap: spacing.lg,
    paddingBottom: spacing.xl,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  info: { flex: 1 },
  name: { fontSize: 15, lineHeight: 20 },
  address: { fontSize: 12, lineHeight: 16, marginTop: 1 },
  remove: {
    width: 32,
    height: 32,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  empty: {
    marginHorizontal: spacing.gutter,
    borderRadius: radius.xl,
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.xl,
  },
  emptyText: {
    fontSize: 13,
    lineHeight: 18,
    textAlign: 'center',
  },
});