import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { Icon, type IconName } from '@/components/Icon';
import { GlassSurface } from '@/components/Glass';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface SectionHeaderProps {
  title: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function SectionHeader({ title, actionLabel, onAction }: SectionHeaderProps) {
  const { theme } = useTheme();

  return (
    <View style={styles.sectionRow}>
      <Text style={[styles.sectionTitle, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.semibold }]}>
        {title.toUpperCase()}
      </Text>
      {actionLabel && onAction ? (
        <Pressable onPress={onAction} accessibilityRole="button">
          <Text style={[styles.sectionAction, { color: theme.colors.primary, fontFamily: fonts.semibold }]}>
            {actionLabel}
          </Text>
        </Pressable>
      ) : null}
    </View>
  );
}

interface SettingRowProps {
  icon: IconName;
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  onPress?: () => void;
}

export function SettingRow({ icon, title, subtitle, trailing, onPress }: SettingRowProps) {
  const { theme } = useTheme();

  const content = (
    <>
      <View style={[styles.rowIcon, { backgroundColor: theme.colors.primaryContainer }]}>
        <Icon name={icon} size={20} color={theme.colors.onPrimaryContainer} />
      </View>
      <View style={styles.rowText}>
        <Text style={[styles.rowTitle, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>{title}</Text>
        {subtitle ? (
          <Text style={[styles.rowSubtitle, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      <View style={styles.rowTrailing}>
        {trailing ?? <Icon name="chevronRight" size={20} color={theme.colors.outline} />}
      </View>
    </>
  );

  const rowStyle = [styles.row, onPress !== undefined && styles.rowPressable];

  if (onPress) {
    return (
      <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [rowStyle, pressed && styles.pressed]}>
        {content}
      </Pressable>
    );
  }
  return <View style={rowStyle}>{content}</View>;
}

interface ToggleRowProps {
  icon?: IconName;
  title: string;
  subtitle?: string;
  value: boolean;
  onValueChange: (value: boolean) => void;
}

export function ToggleRow({ icon, title, subtitle, value, onValueChange }: ToggleRowProps) {
  const { theme } = useTheme();

  return (
    <View style={styles.row}>
      {icon ? (
        <View style={[styles.rowIcon, { backgroundColor: theme.colors.primaryContainer }]}>
          <Icon name={icon} size={20} color={theme.colors.onPrimaryContainer} />
        </View>
      ) : null}
      <View style={styles.rowText}>
        <Text style={[styles.rowTitle, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>{title}</Text>
        {subtitle ? (
          <Text style={[styles.rowSubtitle, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{ true: theme.colors.primary, false: theme.colors.surfaceContainerHighest }}
        thumbColor={theme.colors.surfaceBright}
      />
    </View>
  );
}

export function SettingsGroup({ children }: { children: ReactNode }) {
  const { theme } = useTheme();

  return (
    <GlassSurface variant="floating" style={styles.group}>
      {children}
    </GlassSurface>
  );
}

const styles = StyleSheet.create({
  sectionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.gutter,
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    fontSize: 12,
    letterSpacing: 0.6,
    lineHeight: 16,
  },
  sectionAction: {
    fontSize: 13,
    lineHeight: 16,
  },
  group: {
    borderRadius: radius.xl,
    marginHorizontal: spacing.gutter,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  rowPressable: {
    // padding only; press feedback via opacity below
  },
  rowIcon: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rowText: {
    flex: 1,
  },
  rowTitle: {
    fontSize: 15,
    lineHeight: 20,
  },
  rowSubtitle: {
    fontSize: 12,
    lineHeight: 16,
    marginTop: 1,
  },
  rowTrailing: {
    alignItems: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
});