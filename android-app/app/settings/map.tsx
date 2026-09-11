import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { SettingsGroup, ToggleRow, SectionHeader } from '@/components/SettingsBits';
import { fonts, radius, spacing } from '@/constants/theme';
import { MAP_STYLES, type MapStyleId } from '@/config/map';
import { useTheme } from '@/lib/theme';
import { useNavigationSession } from '@/state/NavigationProvider';

export default function MapSettingsScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { settings, actions } = useNavigationSession();
  const map = settings.map;

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
        <View>
          <ScreenHeader title="Map" onBack={() => router.back()} variant="plain" />
        </View>

        <Text style={[styles.note, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Map style comes from OpenFreeMap (no key needed); satellite uses public Esri imagery.
        </Text>

        <SectionHeader title="Map style" />
        <View style={styles.list}>
          {MAP_STYLES.map((style) => {
            const selected = map.styleId === style.id;
            return (
              <Pressable
                key={style.id}
                onPress={() => actions.updateSettings({ map: { ...map, styleId: style.id } })}
                accessibilityRole="button"
              >
                <GlassSurface
                  style={[
                    styles.option,
                    selected && { backgroundColor: theme.colors.primaryContainer, borderColor: theme.colors.primary },
                  ]}
                >
                  <View
                    style={[styles.swatch, { backgroundColor: selected ? theme.colors.primary : theme.colors.surfaceContainerHigh }]}
                  />
                  <View style={styles.optionText}>
                    <Text style={[styles.optionLabel, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
                      {style.label}
                    </Text>
                    <Text style={[styles.optionHint, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                      {style.previewHint}
                    </Text>
                  </View>
                  <View
                    style={[styles.radio, { borderColor: selected ? theme.colors.primary : theme.colors.outline }]}
                  >
                    {selected ? <View style={[styles.radioDot, { backgroundColor: theme.colors.primary }]} /> : null}
                  </View>
                </GlassSurface>
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
  list: {
    paddingHorizontal: spacing.gutter,
    gap: spacing.sm,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radius.xl,
    padding: spacing.md,
  },
  swatch: {
    width: 52,
    height: 40,
    borderRadius: radius.md,
  },
  optionText: { flex: 1 },
  optionLabel: { fontSize: 15, lineHeight: 20 },
  optionHint: { fontSize: 12, lineHeight: 16, marginTop: 1 },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
});