import type { RecentSearch, SavedPlace } from '@/types/places';

/**
 * Pure operations over saved/recent collections. Storage I/O is handled by
 * the store service; these functions are unit-testable without AsyncStorage.
 */

export const DEFAULT_RECENT_LIMIT = 12;

/** Insert a recent search at the front, de-duplicating by query string. */
export function bumpRecent(
  recents: RecentSearch[],
  entry: RecentSearch,
  limit = DEFAULT_RECENT_LIMIT,
): RecentSearch[] {
  const key = normalizeKey(entry.query);
  const withoutOld = recents.filter((r) => normalizeKey(r.query) !== key);
  return [entry, ...withoutOld].slice(0, limit);
}

/** Remove a recent search by id. */
export function removeRecent(recents: RecentSearch[], id: string): RecentSearch[] {
  return recents.filter((r) => r.id !== id);
}

export function clearRecents(): RecentSearch[] {
  return [];
}

export function findRecent(recents: RecentSearch[], query: string): RecentSearch | undefined {
  const key = normalizeKey(query);
  return recents.find((r) => normalizeKey(r.query) === key);
}

/** Upsert a saved place; home/work replace their same-kind entry. */
export function upsertSavedPlace(places: SavedPlace[], place: SavedPlace): SavedPlace[] {
  const withoutSameId = places.filter((p) => p.id !== place.id);
  if (place.kind === 'home' || place.kind === 'work') {
    const withoutSameKind = withoutSameId.filter((p) => p.kind !== place.kind);
    return [...withoutSameKind, place];
  }
  return [...withoutSameId, place];
}

export function removeSavedPlace(places: SavedPlace[], id: string): SavedPlace[] {
  return places.filter((p) => p.id !== id);
}

export function findSavedPlace(places: SavedPlace[], id: string): SavedPlace | undefined {
  return places.find((p) => p.id === id);
}

/** Stable id generator for new saved places. */
export function makePlaceId(kind: string, name: string): string {
  const stamp = Date.now().toString(36);
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .slice(0, 12);
  return `${kind}-${slug || 'place'}-${stamp}`;
}

export function normalizeKey(query: string): string {
  return query.trim().toLowerCase();
}