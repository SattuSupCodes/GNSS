import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { SettingsGroup, ToggleRow, SectionHeader } from '@/components/SettingsBits';
import { fonts, radius, spacing } from '@/constants/theme';
import { MAP_STYLES } from '@/config/map';
import { useTheme } from '@/lib/theme';
import { useNavigationSession } from '@/state/NavigationProvider';

export default function LayersScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { settings, actions } = useNavigationSession();
  const map = settings.map;

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
        <View>
          <ScreenHeader title="Map Layers" onBack={() => router.back()} variant="plain" />
        </View>

        <Text style={[styles.note, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Vector styles stream from OpenFreeMap. Satellite imagery uses public Esri tiles.
        </Text>

        <SectionHeader title="Style" />
        <View style={styles.chips}>
          {MAP_STYLES.map((style) => {
            const selected = map.styleId === style.id;
            return (
              <Pressable
                key={style.id}
                onPress={() => actions.updateSettings({ map: { ...map, styleId: style.id } })}
                accessibilityRole="button"
                style={({ pressed }) => pressed && { opacity: 0.7 }}
              >
                <View
                  style={[
                    styles.chip,
                    { backgroundColor: selected ? theme.colors.primaryContainer : theme.colors.glassFloating.fill, borderColor: selected ? theme.colors.primary : theme.colors.glassFloating.border },
                  ]}
                >
                  <View
                    style={[
                      styles.dot,
                      { backgroundColor: selected ? theme.colors.primary : theme.colors.outline },
                    ]}
                  />
                  <Text
                    style={[
                      styles.chipLabel,
                      {
                        color: selected ? theme.colors.onPrimaryContainer : theme.colors.onSurface,
                        fontFamily: selected ? fonts.semibold : fonts.medium,
                      },
                    ]}
                  >
                    {style.label}
                  </Text>
                </View>
              </Pressable>
            );
          })}
        </View>

        <SectionHeader title="Behaviour" />
        <SettingsGroup>
          <ToggleRow
            icon="recenter"
            title="Follow my position"
            subtitle="Keep the map centered on your GPS position"
            value={map.followUser}
            onValueChange={(value) => actions.updateSettings({ map: { ...map, followUser: value } })}
          />
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
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    paddingHorizontal: spacing.gutter,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    borderRadius: radius.full,
    borderWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  chipLabel: {
    fontSize: 13,
    lineHeight: 18,
  },
});