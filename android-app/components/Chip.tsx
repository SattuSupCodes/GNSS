import { Pressable, StyleSheet, Text, View } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { Icon, type IconName } from '@/components/Icon';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface ChipProps {
  label: string;
  icon?: IconName;
  selected?: boolean;
  onPress?: () => void;
}

export function Chip({ label, icon, selected = false, onPress }: ChipProps) {
  const { theme } = useTheme();
  const tinted = selected;

  const inner = (
    <GlassSurface
      blurred={false}
      style={[
        styles.chip,
        tinted && { backgroundColor: theme.colors.primaryContainer },
      ]}
    >
      {icon ? (
        <Icon
          name={icon}
          size={16}
          color={tinted ? theme.colors.onPrimaryContainer : theme.colors.onSurfaceVariant}
        />
      ) : null}
      <Text
        style={[
          styles.label,
          {
            fontFamily: tinted ? fonts.semibold : fonts.medium,
            color: tinted ? theme.colors.onPrimaryContainer : theme.colors.onSurface,
          },
        ]}
      >
        {label}
      </Text>
    </GlassSurface>
  );

  if (!onPress) {
    return inner;
  }
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => pressed && styles.pressed}>
      {inner}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
  },
  label: {
    fontSize: 13,
    lineHeight: 18,
  },
  pressed: {
    opacity: 0.7,
  },
});