import { Pressable, StyleSheet, Text, View } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { Icon } from '@/components/Icon';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface SearchBarProps {
  placeholder?: string;
  onPress?: () => void;
}

export function SearchBar({ placeholder = 'Where do you want to go?', onPress }: SearchBarProps) {
  const { theme } = useTheme();

  return (
    <GlassSurface style={styles.bar}>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel="Search destinations"
        style={({ pressed }) => [styles.inner, pressed && styles.pressed]}
      >
        <Icon name="search" size={20} color={theme.colors.onSurfaceVariant} />
        <Text numberOfLines={1} style={[styles.placeholder, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
          {placeholder}
        </Text>
        <View style={styles.mic}>
          <Icon name="mic" size={20} color={theme.colors.onSurface} />
        </View>
      </Pressable>
    </GlassSurface>
  );
}

const styles = StyleSheet.create({
  bar: {
    borderRadius: radius.full,
  },
  inner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingLeft: spacing.lg,
    paddingRight: spacing.sm,
    paddingVertical: spacing.xs,
  },
  placeholder: {
    flex: 1,
    fontSize: 15,
    lineHeight: 20,
  },
  mic: {
    width: 36,
    height: 36,
    borderRadius: radius.full,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'transparent',
  },
  pressed: {
    opacity: 0.7,
  },
});