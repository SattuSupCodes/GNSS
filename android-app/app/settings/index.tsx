import { ScrollView, View } from 'react-native';
import { useRouter } from 'expo-router';

import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { SettingRow, SettingsGroup, SectionHeader } from '@/components/SettingsBits';
import { spacing } from '@/constants/theme';

export default function SettingsScreen() {
  const router = useRouter();

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
        <View>
          <ScreenHeader title="Settings" onBack={() => router.back()} variant="plain" />
        </View>

        <SectionHeader title="Personalisation" />
        <SettingsGroup>
          <SettingRow
            icon="themeAuto"
            title="Appearance"
            subtitle="Light · Dark · Automatic"
            onPress={() => router.push('/settings/appearance')}
          />
          <SettingRow
            icon="map"
            title="Map"
            subtitle="Style, layers & map behaviour"
            onPress={() => router.push('/settings/map')}
          />
          <SettingRow
            icon="route"
            title="Navigation"
            subtitle="Rerouting & arrival behaviour"
            onPress={() => router.push('/settings/navigation')}
          />
          <SettingRow icon="shield" title="Privacy" subtitle="Data sharing preferences" onPress={() => router.push('/settings/privacy')} />
          <SettingRow icon="offline" title="Offline maps" subtitle="Download regions for offline use" onPress={() => router.push('/offline-maps')} />
        </SettingsGroup>

        <SectionHeader title="System" />
        <SettingsGroup>
          <SettingRow
            icon="diagnostics"
            title="Diagnostics & sensors"
            subtitle="Live GPS, sensor and position telemetry"
            onPress={() => router.push('/settings/diagnostics')}
          />
          <SettingRow icon="help" title="About" subtitle="Version, credits & disclaimers" onPress={() => router.push('/settings/about')} />
        </SettingsGroup>
      </ScrollView>
    </Screen>
  );
}