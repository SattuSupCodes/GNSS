import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { Icon } from '@/components/Icon';
import { IconButton } from '@/components/IconButton';
import { Screen } from '@/components/Screen';
import { SectionHeader } from '@/components/SettingsBits';
import { fonts, radius, spacing } from '@/constants/theme';
import { searchResults } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';

export default function SearchScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const [query, setQuery] = useState('');

  const normalized = query.trim().toLowerCase();
  const results = normalized
    ? searchResults.filter(
        (place) => place.name.toLowerCase().includes(normalized) || place.address.toLowerCase().includes(normalized),
      )
    : searchResults;

  return (
    <Screen topInset bottomInset>
      <View style={styles.topRow}>
        <GlassSurface style={styles.inputBar}>
          <Icon name="search" size={20} color={theme.colors.onSurfaceVariant} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search destinations"
            placeholderTextColor={theme.colors.onSurfaceVariant}
            style={[styles.input, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}
            autoFocus
            returnKeyType="search"
          />
          {query.length > 0 ? (
            <Pressable onPress={() => setQuery('')} accessibilityRole="button" hitSlop={12}>
              <Icon name="close" size={18} color={theme.colors.onSurfaceVariant} />
            </Pressable>
          ) : (
            <Icon name="mic" size={20} color={theme.colors.onSurface} />
          )}
        </GlassSurface>
        <IconButton name="close" accessibilityLabel="Close search" variant="plain" onPress={() => router.back()} />
      </View>

      <SectionHeader title={normalized ? 'Results' : 'Popular & recent'} />
      <ScrollView contentContainerStyle={styles.results} keyboardShouldPersistTaps="handled">
        {results.map((place) => (
          <Pressable
            key={place.id}
            onPress={() => router.push({ pathname: '/place', params: { id: place.id } })}
            style={({ pressed }) => [styles.resultRow, pressed && { opacity: 0.7 }]}
          >
            <View style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]}>
              <Icon name="destination" size={20} color={theme.colors.onPrimaryContainer} />
            </View>
            <View style={styles.resultText}>
              <Text numberOfLines={1} style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
                {place.name}
              </Text>
              <Text numberOfLines={1} style={[styles.address, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                {place.address}
              </Text>
            </View>
            <Text style={[styles.category, { color: theme.colors.secondary, fontFamily: fonts.medium }]}>{place.category}</Text>
          </Pressable>
        ))}
        {results.length === 0 ? (
          <Text style={[styles.empty, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            No results for {`\u201c${query}\u201d`}
          </Text>
        ) : null}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.gutter,
    paddingTop: spacing.md,
  },
  inputBar: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    borderRadius: radius.full,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
  input: {
    flex: 1,
    height: 40,
    fontSize: 15,
  },
  results: {
    paddingHorizontal: spacing.gutter,
    paddingBottom: spacing.xl,
  },
  resultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  resultText: { flex: 1 },
  name: { fontSize: 15, lineHeight: 20 },
  address: { fontSize: 12, lineHeight: 16, marginTop: 1 },
  category: { fontSize: 11, lineHeight: 15 },
  empty: {
    marginTop: spacing.xl,
    textAlign: 'center',
  },
});