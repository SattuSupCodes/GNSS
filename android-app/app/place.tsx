import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { PrimaryButton, SecondaryButton } from '@/components/Buttons';
import { Icon } from '@/components/Icon';
import { ScreenHeader } from '@/components/Header';
import { MapCanvas } from '@/components/MapCanvas';
import { Waypoint } from '@/components/MapAnnotations';
import { Screen } from '@/components/Screen';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { addSavedPlace, loadSavedPlaces, deleteSavedPlace } from '@/services/placesStore';
import type { Coordinate } from '@/types/routing';

export default function PlaceScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { name, address, lat, lng, category, source } = useLocalSearchParams() as Record<string, string | undefined>;
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const position: Coordinate | null =
    lat && lng && !Number.isNaN(Number(lat)) && !Number.isNaN(Number(lng))
      ? { latitude: Number(lat), longitude: Number(lng) }
      : null;

  const placeName = name || 'Selected place';
  const placeAddress = address || '';

  useEffect(() => {
    if (!position) return;
    loadSavedPlaces()
      .then((places) => setSaved(places.some((place) => place.position && place.position.latitude === position.latitude && place.position.longitude === position.longitude)))
      .catch(() => {});
  }, [position]);

  function toggleSave() {
    if (!position) return;
    setSaving(true);
    const task = saved
      ? loadSavedPlaces().then((places) => {
          const match = places.find((place) => place.position.latitude === position.latitude && place.position.longitude === position.longitude);
          return match ? deleteSavedPlace(match.id) : places;
        })
      : addSavedPlace({
          id: `saved:${position.latitude}:${position.longitude}`,
          kind: 'favorite',
          name: placeName,
          address: placeAddress,
          position,
          createdAt: Date.now(),
        });
    task.then(() => setSaved((value) => !value)).catch(() => {});
    task.finally(() => setSaving(false));
  }

  if (!position) {
    return (
      <Screen>
        <ScreenHeader title="Place" onBack={() => router.back()} />
        <View style={styles.missing}>
          <Text style={[styles.missingText, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Place coordinates are missing.
          </Text>
        </View>
      </Screen>
    );
  }

  return (
    <Screen topInset={false} bottomInset style={{ backgroundColor: theme.colors.background }}>
      <View style={styles.mapArea}>
        <MapCanvas backdrop="route" />
        <View style={styles.pin} pointerEvents="none">
          <Waypoint icon="destination" size={34} />
        </View>
        <View style={styles.headerOverlay}>
          <ScreenHeader onBack={() => router.back()} title="Place Details" right={<Icon name="more" size={20} />} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>{placeName}</Text>
        <Text style={[styles.category, { color: theme.colors.secondary, fontFamily: fonts.semibold }]}>
          {category || source || 'Place'}
        </Text>
        <View style={styles.addressRow}>
          <Icon name="destination" size={16} color={theme.colors.onSurfaceVariant} />
          <Text style={[styles.address, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            {placeAddress || `${position.latitude.toFixed(5)}, ${position.longitude.toFixed(5)}`}
          </Text>
        </View>

        <View style={[styles.tip, { backgroundColor: theme.colors.primaryContainer }]}>
          <Icon name="info" size={16} color={theme.colors.onPrimaryContainer} />
          <Text style={[styles.tipText, { color: theme.colors.onPrimaryContainer, fontFamily: fonts.medium }]}>
            Routing starts from your current GPS position.
          </Text>
        </View>

        <View style={styles.actions}>
          <PrimaryButton
            icon="forward"
            disabled={!position}
            onPress={() =>
              router.push({
                pathname: '/routing/preview',
                params: { lat: String(position.latitude), lng: String(position.longitude), name: placeName, address: placeAddress },
              })
            }
          >
            Directions
          </PrimaryButton>
          <SecondaryButton icon={saved ? 'saved' : 'savedOutline'} loading={saving} onPress={toggleSave}>
            {saved ? 'Saved' : 'Save'}
          </SecondaryButton>
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  mapArea: {
    height: 300,
  },
  pin: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
  content: {
    padding: spacing.gutter,
    paddingBottom: spacing.xl,
  },
  name: { fontSize: 24, lineHeight: 30 },
  category: { fontSize: 14, lineHeight: 19, marginTop: spacing.xs },
  addressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.md,
  },
  address: { fontSize: 14, lineHeight: 19, flex: 1 },
  tip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginTop: spacing.lg,
  },
  tipText: { flex: 1, fontSize: 13, lineHeight: 18 },
  actions: {
    gap: spacing.md,
    marginTop: spacing.xl,
  },
  missing: { paddingTop: spacing.xl },
  missingText: { textAlign: 'center' },
});