import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { Icon } from '@/components/Icon';
import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { SettingsGroup, SectionHeader } from '@/components/SettingsBits';
import { fonts, radius, spacing } from '@/constants/theme';
import { offlineRegions } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

export default function OfflineMapsScreen() {
  const router = useRouter();
  const { theme } = useTheme();

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
        <View>
          <ScreenHeader title="Offline Maps" onBack={() => router.back()} variant="plain" />
        </View>

        <Text style={[styles.note, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Maps are currently streamed from OpenFreeMap as you drive. Packaged region downloads for full offline navigation are not implemented yet.
        </Text>

        <SectionHeader title="Regions" />
        <SettingsGroup>
          {offlineRegions.map((region) => (
            <View key={region.id} style={styles.row}>
              <View style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]}>
                <Icon name="map" size={20} color={theme.colors.onPrimaryContainer} />
              </View>
              <View style={styles.rowText}>
                <Text numberOfLines={1} style={[styles.rowName, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>
                  {region.name}
                </Text>
                <Text style={[styles.rowSize, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                  {region.sizeMb}
                </Text>
              </View>
              {region.available ? (
                <Pressable onPress={() => {}} accessibilityRole="button" style={({ pressed }) => [styles.downloadBtn, { backgroundColor: theme.colors.primary }, pressed && { opacity: 0.8 }]}>
                  <Icon name="download" size={16} color={theme.colors.onPrimary} />
                  <Text style={[styles.downloadText, { color: theme.colors.onPrimary, fontFamily: fonts.semibold }]}>Download</Text>
                </Pressable>
              ) : (
                <Text style={[styles.soon, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>Soon</Text>
              )}
            </View>
          ))}
        </SettingsGroup>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  note: {
    fontSize: 13,
    lineHeight: 18,
    paddingHorizontal: spacing.gutter,
    marginTop: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowText: { flex: 1 },
  rowName: { fontSize: 15, lineHeight: 20 },
  rowSize: { fontSize: 12, lineHeight: 16, marginTop: 1 },
  downloadBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    borderRadius: radius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
  },
  downloadText: { fontSize: 13, lineHeight: 18 },
  soon: { fontSize: 13, lineHeight: 18 },
});