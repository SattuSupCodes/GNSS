import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { IconButton } from '@/components/IconButton';
import { fonts, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface ScreenHeaderProps {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onBack?: () => void;
  variant?: 'glass' | 'plain';
}

export function ScreenHeader({ title, subtitle, right, onBack, variant = 'glass' }: ScreenHeaderProps) {
  const { theme } = useTheme();

  const content = (
    <>
      <IconButton
        name="back"
        accessibilityLabel="Go back"
        onPress={onBack}
        variant={variant === 'glass' ? 'glass' : 'plain'}
      />
      <View style={styles.textBlock}>
        <Text numberOfLines={1} style={[styles.title, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
          {title}
        </Text>
        {subtitle ? (
          <Text numberOfLines={1} style={[styles.subtitle, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      <View style={styles.right}>{right}</View>
    </>
  );

  if (variant === 'plain') {
    return <View style={styles.plainRow}>{content}</View>;
  }
  return <GlassSurface style={styles.glassRow}>{content}</GlassSurface>;
}

const styles = StyleSheet.create({
  glassRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: 999,
    marginHorizontal: spacing.gutter,
  },
  plainRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  textBlock: {
    flex: 1,
    paddingHorizontal: spacing.md,
  },
  title: {
    fontSize: 18,
    lineHeight: 22,
  },
  subtitle: {
    fontSize: 12,
    lineHeight: 16,
  },
  right: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
});