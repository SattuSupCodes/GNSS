import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';

import { PrimaryButton, SecondaryButton } from '@/components/Buttons';
import { Icon } from '@/components/Icon';
import { ScreenHeader } from '@/components/Header';
import { MapCanvas } from '@/components/MapCanvas';
import { Waypoint } from '@/components/MapAnnotations';
import { Screen } from '@/components/Screen';
import { fonts, radius, spacing } from '@/constants/theme';
import { recentDestinations, searchResults } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

export default function PlaceScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const [saved, setSaved] = useState(false);

  const place =
    searchResults.find((item) => item.id === id) ?? recentDestinations.find((item) => item.id === id);

  if (!place) {
    return (
      <Screen>
        <ScreenHeader title="Place" onBack={() => router.back()} />
        <View style={styles.missing}>
          <Text style={[styles.missingText, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Place not found
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
        <Text style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>{place.name}</Text>
        <Text style={[styles.category, { color: theme.colors.secondary, fontFamily: fonts.semibold }]}>
          {place.category}
        </Text>
        <View style={styles.addressRow}>
          <Icon name="destination" size={16} color={theme.colors.onSurfaceVariant} />
          <Text style={[styles.address, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            {place.address}
          </Text>
        </View>
        {place.sublabel ? (
          <View style={[styles.tip, { backgroundColor: theme.colors.primaryContainer }]}>
            <Icon name="info" size={16} color={theme.colors.onPrimaryContainer} />
            <Text style={[styles.tipText, { color: theme.colors.onPrimaryContainer, fontFamily: fonts.medium }]}>
              {place.sublabel}
            </Text>
          </View>
        ) : null}

        <View style={styles.actions}>
          <PrimaryButton icon="forward" onPress={() => router.push('/routing/preview')}>
            Directions
          </PrimaryButton>
          <SecondaryButton
            icon={saved ? 'saved' : 'savedOutline'}
            onPress={() => setSaved((value) => !value)}
          >
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