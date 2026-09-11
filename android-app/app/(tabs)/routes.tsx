import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { Icon, IconName } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { spacing, fonts, radius } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { loadSavedPlaces } from '@/services/placesStore';
import type { SavedPlace, SavedPlaceKind } from '@/types/places';

const KIND_ICON: Record<SavedPlaceKind, IconName> = {
  home: 'home',
  work: 'work',
  favorite: 'star',
};

export default function RoutesScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const [places, setPlaces] = useState<SavedPlace[]>([]);

  useEffect(() => {
    loadSavedPlaces().then(setPlaces);
  }, []);

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>Routes</Text>
        <Text style={[styles.subtitle, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Plan a route from your saved places.
        </Text>
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
            style={({ pressed }) => [styles.card, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }, pressed && { opacity: 0.8 }]}
          >
            <View style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]}>
              <Icon name={KIND_ICON[place.kind]} size={20} color={theme.colors.onPrimaryContainer} />
            </View>
            <View style={styles.info}>
              <Text numberOfLines={1} style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>{place.name}</Text>
              <Text numberOfLines={1} style={[styles.meta, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>{place.address}</Text>
            </View>
            <View style={styles.action}>
              <Text style={[styles.go, { color: theme.colors.primary, fontFamily: fonts.bold }]}>Go</Text>
            </View>
            <Icon name="chevronRight" size={18} color={theme.colors.outline} />
          </Pressable>
        ))}

        {places.length === 0 ? (
          <GlassSurface style={styles.empty}>
            <Icon name="route" size={22} color={theme.colors.onSurfaceVariant} />
            <Text style={[styles.emptyText, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
              Save a place (Home, Work or a favorite) and it will appear here as a one-tap route.
            </Text>
          </GlassSurface>
        ) : null}
      </ScrollView>
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
  subtitle: { fontSize: 13, lineHeight: 18, marginTop: 2 },
  list: {
    paddingHorizontal: spacing.gutter,
    gap: spacing.md,
    paddingBottom: spacing.xl,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
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
  meta: { fontSize: 12, lineHeight: 16, marginTop: 1 },
  action: {
    borderRadius: radius.full,
    backgroundColor: 'transparent',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  go: { fontSize: 14, lineHeight: 18 },
  empty: {
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