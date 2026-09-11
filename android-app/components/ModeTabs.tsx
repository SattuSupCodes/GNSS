import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { GlassSurface } from '@/components/Glass';
import { Icon, type IconName } from '@/components/Icon';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

export interface ModeOption {
  id: string;
  label: string;
  icon: IconName;
  duration?: string;
}

interface ModeTabsProps {
  options: ModeOption[];
  value: string;
  onChange: (id: string) => void;
}

export function ModeTabs({ options, value, onChange }: ModeTabsProps) {
  const { theme } = useTheme();

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {options.map((option) => {
        const selected = option.id === value;
        const color = selected ? theme.colors.onPrimaryContainer : theme.colors.onSurface;
        return (
          <Pressable
            key={option.id}
            onPress={() => onChange(option.id)}
            accessibilityRole="button"
            style={({ pressed }) => pressed && styles.pressed}
          >
            <GlassSurface
              blurred={false}
              style={[
                styles.tab,
                selected && { backgroundColor: theme.colors.primaryContainer },
              ]}
            >
              <Icon name={option.icon} size={18} color={color} />
              <Text style={[styles.label, { color, fontFamily: selected ? fonts.semibold : fonts.medium }]}>
                {option.label}
              </Text>
              {option.duration ? (
                <Text style={[styles.duration, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
                  {option.duration}
                </Text>
              ) : null}
            </GlassSurface>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.gutter,
  },
  tab: {
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
    textTransform: 'capitalize',
  },
  duration: {
    fontSize: 11,
    lineHeight: 16,
  },
  pressed: {
    opacity: 0.7,
  },
});