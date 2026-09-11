import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { ScreenHeader } from '@/components/Header';
import { Icon, type IconName } from '@/components/Icon';
import { Screen } from '@/components/Screen';
import { fonts, radius, spacing } from '@/constants/theme';
import type { AppearanceMode } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

const OPTIONS: { value: AppearanceMode; icon: IconName; label: string; hint: string }[] = [
  { value: 'system', icon: 'themeAuto', label: 'Automatic', hint: 'Follows your device setting' },
  { value: 'light', icon: 'themeLight', label: 'Light', hint: 'Bright, airy surface palette' },
  { value: 'dark', icon: 'themeDark', label: 'Dark', hint: 'Tactical aerospace palette' },
];

export default function AppearanceScreen() {
  const router = useRouter();
  const { theme, appearance, setAppearance } = useTheme();

  return (
    <Screen>
      <View>
        <ScreenHeader title="Appearance" onBack={() => router.back()} variant="plain" />
      </View>

      <View style={styles.list}>
        {OPTIONS.map((option) => {
          const selected = appearance === option.value;
          return (
            <Pressable key={option.value} onPress={() => setAppearance(option.value)} accessibilityRole="button">
              <GlassSurface
                style={[
                  styles.option,
                  selected && {
                    backgroundColor: theme.colors.primaryContainer,
                    borderColor: theme.colors.primary,
                  },
                ]}
              >
                <View style={[styles.iconWrap, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
                  <Icon name={option.icon} size={22} color={selected ? theme.colors.primary : theme.colors.onSurfaceVariant} />
                </View>
                <View style={styles.optionText}>
                  <Text style={[styles.optionLabel, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
                    {option.label}
                  </Text>
                  <Text style={[styles.optionHint, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                    {option.hint}
                  </Text>
                </View>
                <View
                  style={[
                    styles.radio,
                    { borderColor: selected ? theme.colors.primary : theme.colors.outline },
                  ]}
                >
                  {selected ? <View style={[styles.radioDot, { backgroundColor: theme.colors.primary }]} /> : null}
                </View>
              </GlassSurface>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.previewCard}>
        <GlassSurface style={styles.preview}>
          <View style={{ flexDirection: 'row', gap: spacing.sm, alignItems: 'center' }}>
            <View style={[styles.swatch, { backgroundColor: theme.colors.surfaceContainerLowest }]} />
            <View style={{ flex: 1 }}>
              <View style={[styles.line, { backgroundColor: theme.colors.onSurface, opacity: 0.85 }]} />
              <View style={[styles.line, { backgroundColor: theme.colors.onSurfaceVariant, opacity: 0.4 }]} />
            </View>
          </View>
        </GlassSurface>
        <Text style={[styles.previewLabel, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          Live preview
        </Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    paddingHorizontal: spacing.gutter,
    gap: spacing.md,
    marginTop: spacing.lg,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radius.xl,
    padding: spacing.lg,
  },
  iconWrap: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionText: { flex: 1 },
  optionLabel: { fontSize: 16, lineHeight: 21 },
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
  previewCard: {
    paddingHorizontal: spacing.gutter,
    marginTop: spacing.xl,
    gap: spacing.sm,
  },
  preview: {
    borderRadius: radius.xl,
    padding: spacing.lg,
  },
  swatch: {
    width: 130,
    height: 84,
    borderRadius: radius.lg,
  },
  line: {
    height: 10,
    borderRadius: 5,
    marginBottom: 8,
    width: '70%',
  },
  previewLabel: {
    fontSize: 12,
    lineHeight: 16,
    textAlign: 'center',
  },
});