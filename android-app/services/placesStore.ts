import { bumpRecent, removeRecent, upsertSavedPlace, removeSavedPlace, clearRecents } from '@/core/places';
import { readJson, writeJson } from '@/services/storage';
import type { RecentSearch, SavedPlace } from '@/types/places';

/**
 * Persisted places store (saved places + recent searches). Pure collection
 * logic lives in core/places; this module owns AsyncStorage keys and reads.
 */

export const SAVED_PLACES_KEY = 'navsphere.savedPlaces';
export const RECENT_SEARCHES_KEY = 'navsphere.recentSearches';

export async function loadSavedPlaces(): Promise<SavedPlace[]> {
  return readJson<SavedPlace[]>(SAVED_PLACES_KEY, []);
}

export async function savePlaces(places: SavedPlace[]): Promise<void> {
  await writeJson(SAVED_PLACES_KEY, places);
}

export async function addSavedPlace(place: SavedPlace): Promise<SavedPlace[]> {
  const next = upsertSavedPlace(await loadSavedPlaces(), place);
  await savePlaces(next);
  return next;
}

export async function deleteSavedPlace(id: string): Promise<SavedPlace[]> {
  const next = removeSavedPlace(await loadSavedPlaces(), id);
  await savePlaces(next);
  return next;
}

export async function loadRecentSearches(): Promise<RecentSearch[]> {
  return readJson<RecentSearch[]>(RECENT_SEARCHES_KEY, []);
}

export async function saveRecents(recents: RecentSearch[]): Promise<void> {
  await writeJson(RECENT_SEARCHES_KEY, recents);
}

export async function pushRecentSearch(entry: RecentSearch): Promise<RecentSearch[]> {
  const next = bumpRecent(await loadRecentSearches(), entry);
  await saveRecents(next);
  return next;
}

export async function deleteRecentSearch(id: string): Promise<RecentSearch[]> {
  const next = removeRecent(await loadRecentSearches(), id);
  await saveRecents(next);
  return next;
}

export async function purgeRecentSearches(): Promise<void> {
  await writeJson(RECENT_SEARCHES_KEY, clearRecents());
}