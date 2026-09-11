import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { Icon } from '@/components/Icon';
import { IconButton } from '@/components/IconButton';
import { Screen } from '@/components/Screen';
import { SectionHeader } from '@/components/SettingsBits';
import { fonts, radius, spacing } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import { demoSearchProvider } from '@/services/routing/demoSearchService';
import { searchProvider } from '@/services/routing/searchService';
import { loadRecentSearches, purgeRecentSearches, pushRecentSearch } from '@/services/placesStore';
import { useNavigationSession } from '@/state/NavigationProvider';
import type { SearchResult } from '@/types/search';
import type { RecentSearch } from '@/types/places';

export default function SearchScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { demoMode } = useNavigationSession();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [recents, setRecents] = useState<RecentSearch[]>([]);

  const provider = demoMode ? demoSearchProvider : searchProvider;
  const normalized = query.trim();

  useEffect(() => {
    loadRecentSearches().then(setRecents);
  }, []);

  useEffect(() => {
    if (!normalized) {
      setResults([]);
      setErrorMsg(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const controller = new AbortController();
    const timer = setTimeout(() => {
      provider
        .search(normalized, { limit: 7, signal: controller.signal })
        .then((next) => {
          setResults(next);
          setErrorMsg(null);
        })
        .catch((error: unknown) => {
          if (error instanceof Error && error.name === 'AbortError') return;
          setErrorMsg(error instanceof Error ? error.message : 'Search failed.');
        })
        .finally(() => setSearching(false));
    }, 350);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, demoMode, provider, normalized]);

  function openResult(result: SearchResult) {
    if (result.position) {
      pushRecentSearch({
        id: result.id,
        query: result.name,
        name: result.name,
        position: result.position,
        searchedAt: Date.now(),
      }).then(setRecents);
    }
    router.push({
      pathname: '/place',
      params: {
        name: result.name,
        address: result.address,
        lat: String(result.position?.latitude ?? ''),
        lng: String(result.position?.longitude ?? ''),
        category: result.category ?? '',
        source: result.sourceLabel,
      },
    });
  }

  function openRecent(recent: RecentSearch) {
    if (recent.position) {
      router.push({
        pathname: '/routing/preview',
        params: {
          lat: String(recent.position.latitude),
          lng: String(recent.position.longitude),
          name: recent.name,
          address: recent.query || recent.name,
        },
      });
    }
  }

  const showRecents = !normalized;

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

      {demoMode ? (
        <Text style={[styles.demoNote, { color: theme.colors.secondary, fontFamily: fonts.medium }]}>
          Demo mode: searching sample places offline.
        </Text>
      ) : null}

      {errorMsg ? (
        <Text style={[styles.empty, { color: theme.colors.error, fontFamily: fonts.medium }]}>{errorMsg}</Text>
      ) : null}

      <SectionHeader title={normalized ? 'Results' : 'Recent searches'} actionLabel={showRecents && recents.length > 0 ? 'Clear' : undefined} onAction={showRecents && recents.length > 0 ? () => purgeRecentSearches().then(() => setRecents([])) : undefined} />

      <ScrollView contentContainerStyle={styles.results} keyboardShouldPersistTaps="handled">
        {searching ? (
          <ActivityIndicator style={{ paddingTop: spacing.xl }} color={theme.colors.primary} />
        ) : null}

        {showRecents && !searching
          ? recents.map((recent) => (
              <Pressable
                key={recent.id}
                onPress={() => openRecent(recent)}
                style={({ pressed }) => [styles.resultRow, pressed && { opacity: 0.7 }]}
              >
                <View style={[styles.iconWrap, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
                  <Icon name="history" size={20} color={theme.colors.primary} />
                </View>
                <View style={styles.resultText}>
                  <Text numberOfLines={1} style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
                    {recent.name}
                  </Text>
                  <Text numberOfLines={1} style={[styles.address, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                    {recent.query}
                  </Text>
                </View>
                <Icon name="chevronRight" size={18} color={theme.colors.outline} />
              </Pressable>
            ))
          : null}

        {!showRecents && !searching
          ? results.map((result) => (
              <Pressable
                key={result.id}
                onPress={() => openResult(result)}
                style={({ pressed }) => [styles.resultRow, pressed && { opacity: 0.7 }]}
              >
                <View style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]}>
                  <Icon name="destination" size={20} color={theme.colors.onPrimaryContainer} />
                </View>
                <View style={styles.resultText}>
                  <Text numberOfLines={1} style={[styles.name, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
                    {result.name}
                  </Text>
                  <Text numberOfLines={1} style={[styles.address, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
                    {result.address}
                  </Text>
                </View>
                <Text style={[styles.category, { color: theme.colors.secondary, fontFamily: fonts.medium }]}>
                  {result.category ?? result.sourceLabel}
                </Text>
              </Pressable>
            ))
          : null}

        {!showRecents && !searching && normalized.length > 0 && results.length === 0 && !errorMsg ? (
          <Text style={[styles.empty, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            No results for {`\u201c${query}\u201d`}
          </Text>
        ) : null}

        {showRecents && !searching && recents.length === 0 && !errorMsg ? (
          <Text style={[styles.empty, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            No recent searches yet.
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
  demoNote: {
    paddingHorizontal: spacing.gutter,
    marginTop: spacing.sm,
    fontSize: 12,
    lineHeight: 16,
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