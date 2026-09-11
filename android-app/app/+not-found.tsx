import { StyleSheet, Text, View } from 'react-native';
import { Link } from 'expo-router';

import { PrimaryButton } from '@/components/Buttons';
import { NavSphereLogo } from '@/components/NavSphereLogo';
import { Screen } from '@/components/Screen';
import { fonts, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

export default function NotFoundScreen() {
  const { theme } = useTheme();

  return (
    <Screen style={styles.screen}>
      <NavSphereLogo size={56} />
      <Text style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.bold }]}>
        Screen not found
      </Text>
      <Text style={[styles.body, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
        The route you requested does not exist.
      </Text>
      <Link href="/" asChild>
        <PrimaryButton style={styles.button}>Back to Explore</PrimaryButton>
      </Link>
    </Screen>
  );
}

const styles = StyleSheet.create({
  screen: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  title: {
    fontSize: 20,
    lineHeight: 26,
  },
  body: {
    fontSize: 14,
    lineHeight: 19,
  },
  button: {
    marginTop: spacing.lg,
  },
});