import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { Icon } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { spacing, fonts, radius } from '@/constants/theme';
import { savedPlaces } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

export default function SavedScreen() {
  const router = useRouter();
  const { theme } = useTheme();

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>Saved Places</Text>
      </View>

      <ScrollView contentContainerStyle={styles.list}>
        {savedPlaces.map((place) => (
          <Pressable
            key={place.id}
            onPress={() => router.push({ pathname: '/place', params: { id: place.id } })}
            style={({ pressed }) => [styles.row, pressed && { opacity: 0.7 }]}
          >
            <View style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]}>
              <Icon name={place.icon} size={20} color={theme.colors.onPrimaryContainer} />
            </View>
            <View style={styles.info}>
              <Text numberOfLines={1} style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>{place.name}</Text>
              <Text numberOfLines={1} style={[styles.address, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>{place.address}</Text>
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
});