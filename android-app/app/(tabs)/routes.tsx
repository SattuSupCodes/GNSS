import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { Icon } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { spacing, fonts, radius } from '@/constants/theme';
import { demoRouteCards } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

export default function RoutesScreen() {
  const router = useRouter();
  const { theme } = useTheme();

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>Saved Routes</Text>
      </View>

      <ScrollView contentContainerStyle={styles.list}>
        {demoRouteCards.map((route) => (
          <Pressable
            key={route.id}
            onPress={() => router.push('/routing/preview')}
            style={({ pressed }) => [styles.card, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }, pressed && { opacity: 0.8 }]}
          >
            <View style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]}>
              <Icon name={route.icon} size={20} color={theme.colors.onPrimaryContainer} />
            </View>
            <View style={styles.info}>
              <Text numberOfLines={1} style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>{route.destinationLabel}</Text>
              <Text numberOfLines={1} style={[styles.meta, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>{route.title}</Text>
            </View>
            <View style={styles.durationWrap}>
              <Text style={[styles.duration, { color: theme.colors.primary, fontFamily: fonts.bold }]}>{route.duration}</Text>
              <Text style={[styles.distance, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>{route.distanceKm}</Text>
            </View>
            <Icon name="chevronRight" size={18} color={theme.colors.outline} />
          </Pressable>
        ))}
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
  durationWrap: { alignItems: 'flex-end' },
  duration: { fontSize: 16, lineHeight: 20 },
  distance: { fontSize: 12, lineHeight: 16 },
});