import { Tabs } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { GlassSurface } from '@/components/Glass';
import { Icon, type IconName } from '@/components/Icon';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';

interface TabNavLike {
  state: { routes: { key: string; name: string }[]; index: number };
  navigation: {
    emit: (event: {
      type: 'tabPress';
      target: string;
      canPreventDefault: true;
    }) => { defaultPrevented: boolean };
    navigate: (name: string) => void;
  };
}

const TAB_DEFS: { route: string; icon: IconName; label: string }[] = [
  { route: 'index', icon: 'explore', label: 'Explore' },
  { route: 'routes', icon: 'route', label: 'Routes' },
  { route: 'saved', icon: 'saved', label: 'Saved' },
  { route: 'profile', icon: 'profile', label: 'Profile' },
];

function GlassTabBar({ state, navigation }: TabNavLike) {
  const { theme } = useTheme();
  const insets = useSafeAreaInsets();
  const currentRoute = state.routes[state.index].name;

  return (
    <View style={[styles.wrap, { bottom: insets.bottom + spacing.md }]}>
      <GlassSurface variant="tactical" style={styles.bar}>
        {TAB_DEFS.map(({ route, icon, label }) => {
          const focused = currentRoute === route;
          const color = focused ? theme.colors.primary : theme.colors.onSurfaceVariant;
          return (
            <Pressable
              key={route}
              accessibilityRole="button"
              accessibilityLabel={label}
              onPress={() => {
                const event = navigation.emit({
                  type: 'tabPress',
                  target: state.routes[state.index].key,
                  canPreventDefault: true,
                });
                if (!event.defaultPrevented) {
                  navigation.navigate(route);
                }
              }}
              style={({ pressed }) => [styles.tab, pressed && { opacity: 0.7 }]}
            >
              <Icon name={icon} size={22} color={color} />
              <Text style={[styles.label, { color, fontFamily: focused ? fonts.semibold : fonts.medium }]}>{label}</Text>
              {focused ? <View style={[styles.indicator, { backgroundColor: theme.colors.primary }]} /> : null}
            </Pressable>
          );
        })}
      </GlassSurface>
    </View>
  );
}

export default function TabLayout() {
  return (
    <Tabs tabBar={(props) => <GlassTabBar {...props} />} screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="index" />
      <Tabs.Screen name="routes" />
      <Tabs.Screen name="saved" />
      <Tabs.Screen name="profile" />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: spacing.gutter,
    right: spacing.gutter,
    zIndex: 50,
  },
  bar: {
    flexDirection: 'row',
    borderRadius: radius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.xs,
  },
  label: {
    fontSize: 11,
    lineHeight: 15,
    marginTop: 2,
  },
  indicator: {
    marginTop: 3,
    width: 22,
    height: 2.5,
    borderRadius: radius.full,
  },
});