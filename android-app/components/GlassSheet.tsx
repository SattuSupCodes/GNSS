import type { PropsWithChildren } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface GlassSheetProps extends PropsWithChildren {
  style?: StyleProp<ViewStyle>;
}

export function GlassSheet({ children, style }: GlassSheetProps) {
  const { theme } = useTheme();

  return (
    <GlassSurface variant="sheet" style={[styles.sheet, style]}>
      <View style={[styles.handle, { backgroundColor: theme.colors.outlineVariant }]} />
      {children}
    </GlassSurface>
  );
}

const styles = StyleSheet.create({
  sheet: {
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xl,
    borderBottomLeftRadius: radius.lg,
    borderBottomRightRadius: radius.lg,
  },
  handle: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: radius.full,
    marginBottom: spacing.md,
  },
});