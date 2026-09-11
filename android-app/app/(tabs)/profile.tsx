import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { SettingRow, SettingsGroup, SectionHeader } from '@/components/SettingsBits';
import { NavSphereLogo, NavSphereWordmark } from '@/components/NavSphereLogo';
import { spacing, fonts } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

export default function ProfileScreen() {
  const router = useRouter();
  const { theme } = useTheme();

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.brandRow}>
          <NavSphereLogo size={52} />
          <View style={styles.brandText}>
            <NavSphereWordmark />
            <Text style={[styles.sub, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
              Precision navigation prototype
            </Text>
          </View>
        </View>

        <SectionHeader title="Settings" />
        <SettingsGroup>
          <SettingRow icon="tune" title="Settings" subtitle="Appearance, offline maps & more" onPress={() => router.push('/settings')} />
        </SettingsGroup>

        <SectionHeader title="System" />
        <SettingsGroup>
          <SettingRow
            icon="diagnostics"
            title="Diagnostics & sensors"
            subtitle="Technical telemetry board"
            onPress={() => router.push('/settings/diagnostics')}
          />
          <SettingRow
            icon="help"
            title="About"
            subtitle="Version, credits & disclaimers"
            onPress={() => router.push('/settings/about')}
          />
        </SettingsGroup>

        <Text style={[styles.footer, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
          NavSphere IDR Navigation App · ISRO SIH 2026
        </Text>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.gutter,
    paddingTop: spacing.xl,
    paddingBottom: spacing.xl,
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
    marginBottom: spacing.xl,
  },
  brandText: { flex: 1 },
  sub: { fontSize: 13, lineHeight: 18, marginTop: spacing.xs },
  footer: {
    marginTop: spacing.xl,
    textAlign: 'center',
    fontSize: 12,
    lineHeight: 16,
  },
});