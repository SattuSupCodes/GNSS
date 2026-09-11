import { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { SettingsGroup, ToggleRow, SectionHeader } from '@/components/SettingsBits';
import { fonts, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface LayerToggle {
  id: string;
  title: string;
  subtitle: string;
}

const LAYERS: LayerToggle[] = [
  { id: 'traffic', title: 'Traffic', subtitle: 'Live traffic conditions' },
  { id: 'transit', title: 'Transit lines', subtitle: 'Metro & bus routes' },
  { id: 'satellite', title: 'Satellite imagery', subtitle: 'High-resolution aerial view' },
  { id: 'poi', title: 'Landmarks & POIs', subtitle: 'Popular places' },
];

export default function LayersScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const [state, setState] = useState<Record<string, boolean>>({ traffic: true, transit: false, satellite: false, poi: true });

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
        <View>
          <ScreenHeader title="Map Layers" onBack={() => router.back()} variant="plain" />
        </View>

        <Text style={[styles.note, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Preference preview — rendering arrives with the MapLibre engine phase.
        </Text>

        <SectionHeader title="Layers" />
        <SettingsGroup>
          {LAYERS.map((layer) => (
            <ToggleRow
              key={layer.id}
              title={layer.title}
              subtitle={layer.subtitle}
              value={state[layer.id]}
              onValueChange={(value) => setState((prev) => ({ ...prev, [layer.id]: value }))}
            />
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
});