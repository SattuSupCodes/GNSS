import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';

import { Icon, type IconName } from '@/components/Icon';
import { radius } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface IconButtonProps {
  name: IconName;
  accessibilityLabel: string;
  onPress?: () => void;
  size?: number;
  variant?: 'glass' | 'plain';
  style?: StyleProp<ViewStyle>;
}

export function IconButton({
  name,
  accessibilityLabel,
  onPress,
  size = 22,
  variant = 'glass',
  style,
}: IconButtonProps) {
  const { theme } = useTheme();
  const glass = variant === 'glass';

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      onPress={onPress}
      hitSlop={8}
      style={({ pressed }) => [
        styles.button,
        glass && {
          backgroundColor: theme.colors.glassFloating.fill,
          borderColor: theme.colors.glassFloating.border,
          borderWidth: StyleSheet.hairlineWidth,
        },
        glass && styles.round,
        pressed && styles.pressed,
        style,
      ]}
    >
      <Icon name={name} size={size} color={glass ? theme.colors.onSurface : theme.colors.onSurfaceVariant} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    width: 44,
    height: 44,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  round: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
});