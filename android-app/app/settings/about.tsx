import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { SectionHeader, SettingsGroup } from '@/components/SettingsBits';
import { NavSphereLogo, NavSphereWordmark } from '@/components/NavSphereLogo';
import { spacing, fonts, radius } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

export default function AboutScreen() {
  const router = useRouter();
  const { theme } = useTheme();

  return (
    <Screen>
      <View>
        <ScreenHeader title="About" onBack={() => router.back()} variant="plain" />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={[styles.hero, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }]}>
          <NavSphereLogo size={72} />
          <NavSphereWordmark />
          <Text style={[styles.tagline, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Dead-reckoning navigation for urban canyons, tunnels and underpasses.
          </Text>
          <View style={[styles.badge, { backgroundColor: theme.colors.primaryContainer }]}>
            <Text style={[styles.badgeText, { color: theme.colors.onPrimaryContainer, fontFamily: fonts.bold }]}>
              ISRO SIH 2026
            </Text>
          </View>
        </View>

        <SectionHeader title="Team" />
        <SettingsGroup>
          <Text style={[styles.row, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>Shatakshi Sahu — Inertial dead-reckoning engine</Text>
          <Text style={[styles.row, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>Tanishk — Positioning & ML fusion</Text>
        </SettingsGroup>

        <SectionHeader title="Status" />
        <SettingsGroup>
          <Text style={[styles.row, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>UI preview build v1.0.0</Text>
          <Text style={[styles.row, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            GNSS, IDR, map engine and routing are engineering-phase, not active in this preview.
          </Text>
        </SettingsGroup>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingBottom: spacing.xl,
  },
  hero: {
    alignItems: 'center',
    gap: spacing.sm,
    marginHorizontal: spacing.gutter,
    marginTop: spacing.lg,
    padding: spacing.xl,
    borderRadius: radius.xl,
    borderWidth: StyleSheet.hairlineWidth,
  },
  tagline: {
    textAlign: 'center',
    fontSize: 13,
    lineHeight: 18,
  },
  badge: {
    marginTop: spacing.sm,
    borderRadius: radius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
  badgeText: {
    fontSize: 13,
    lineHeight: 18,
  },
  row: {
    fontSize: 14,
    lineHeight: 20,
    paddingVertical: spacing.sm,
  },
});