import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { SettingsGroup, ToggleRow, SectionHeader } from '@/components/SettingsBits';
import { fonts, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { useNavigationSession } from '@/state/NavigationProvider';

export default function PrivacySettingsScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { settings, actions } = useNavigationSession();
  const privacy = settings.privacy;

  return (
    <Screen>
      <ScrollView contentContainerStyle={{ paddingBottom: spacing.xl }}>
        <View>
          <ScreenHeader title="Privacy" onBack={() => router.back()} variant="plain" />
        </View>

        <Text style={[styles.note, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Your location is used locally for navigation. GraphHopper receives only the origin and destination coordinates needed to compute a route.
        </Text>

        <SectionHeader title="Data sharing" />
        <SettingsGroup>
          <ToggleRow
            icon="shield"
            title="Share anonymous analytics"
            subtitle="Optional, off by default"
            value={privacy.shareAnalytics}
            onValueChange={(value) => actions.updateSettings({ privacy: { ...privacy, shareAnalytics: value } })}
          />
        </SettingsGroup>

        <Text style={[styles.footnote, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
          No route history or trip data leaves this device.
        </Text>
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
  footnote: {
    fontSize: 12,
    lineHeight: 16,
    paddingHorizontal: spacing.gutter,
    marginTop: spacing.lg,
  },
});