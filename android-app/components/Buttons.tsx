import type { PropsWithChildren } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, type StyleProp, type ViewStyle } from 'react-native';

import { Icon, type IconName } from '@/components/Icon';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface ButtonProps extends PropsWithChildren {
  onPress?: () => void;
  icon?: IconName;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function PrimaryButton({ onPress, icon, disabled, loading, style, children }: ButtonProps) {
  const { theme } = useTheme();

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: theme.colors.primary, opacity: disabled ? 0.5 : pressed ? 0.85 : 1 },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={theme.colors.onPrimary} />
      ) : (
        <>
          {icon ? <Icon name={icon} size={20} color={theme.colors.onPrimary} /> : null}
          <Text style={[styles.label, { color: theme.colors.onPrimary, fontFamily: fonts.semibold }]}>{children}</Text>
        </>
      )}
    </Pressable>
  );
}

export function SecondaryButton({ onPress, icon, disabled, style, children }: ButtonProps) {
  const { theme } = useTheme();

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        styles.secondary,
        {
          backgroundColor: theme.colors.glassFloating.fill,
          borderColor: theme.colors.glassFloating.border,
          opacity: pressed ? 0.8 : 1,
        },
        style,
      ]}
    >
      {icon ? <Icon name={icon} size={20} /> : null}
      <Text style={[styles.label, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>{children}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    height: 54,
    borderRadius: radius.full,
    paddingHorizontal: spacing.xl,
  },
  secondary: {
    borderWidth: StyleSheet.hairlineWidth,
  },
  label: {
    fontSize: 16,
    lineHeight: 22,
  },
});