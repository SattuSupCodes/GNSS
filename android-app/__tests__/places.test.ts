import { bumpRecent, clearRecents, findRecent, removeRecent, upsertSavedPlace, removeSavedPlace, findSavedPlace, makePlaceId, normalizeKey } from '@/core/places';
import type { RecentSearch, SavedPlace } from '@/types/places';

function recent(query: string, overrides: Partial<RecentSearch> = {}): RecentSearch {
  return { id: `r-${query}`, query, name: query, position: null, searchedAt: 0, ...overrides };
}

function place(id: string, kind: SavedPlace['kind'] = 'favorite'): SavedPlace {
  return { id, kind, name: id, address: '', position: { latitude: 25, longitude: 55 }, createdAt: 0 };
}

describe('bumpRecent', () => {
  it('prepends and de-duplicates by query', () => {
    const input = [recent('old'), recent('Burj')];
    const out = bumpRecent(input, recent('burj'));
    expect(out).toHaveLength(2);
    expect(out[0].query).toBe('burj');
  });

  it('respects the limit', () => {
    const input = Array.from({ length: 10 }, (_, i) => recent(`q${i}`));
    const out = bumpRecent(input, recent('new'), 5);
    expect(out).toHaveLength(5);
    expect(out[0].query).toBe('new');
  });
});

describe('removeRecent / clearRecents / findRecent', () => {
  it('removes by id and clears', () => {
    const input = [recent('a'), recent('b')];
    expect(removeRecent(input, 'r-a')).toHaveLength(1);
    expect(clearRecents()).toEqual([]);
  });

  it('finds case-insensitively and normalizes keys', () => {
    expect(findRecent([recent('DIFC')], 'difc')?.query).toBe('DIFC');
  });

  it('normalizeKey trims and lowercases', () => {
    expect(normalizeKey('  Burj Khalifa ')).toBe('burj khalifa');
  });
});

describe('upsertSavedPlace', () => {
  it('adds a new place', () => {
    const out = upsertSavedPlace([], place('p1'));
    expect(out).toHaveLength(1);
  });

  it('replaces same id', () => {
    const out = upsertSavedPlace([place('p1', 'favorite')], { ...place('p1', 'favorite'), name: 'Renamed' });
    expect(out).toHaveLength(1);
    expect(out[0].name).toBe('Renamed');
  });

  it('replaces same kind for home/work', () => {
    const out = upsertSavedPlace([place('home-old', 'home')], place('home-new', 'home'));
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe('home-new');
  });

  it('keeps both favorite places', () => {
    const out = upsertSavedPlace([place('p1', 'favorite')], place('p2', 'favorite'));
    expect(out).toHaveLength(2);
  });
});

describe('removeSavedPlace / findSavedPlace', () => {
  it('removes and finds', () => {
    const input = [place('p1'), place('p2')];
    expect(removeSavedPlace(input, 'p1')).toHaveLength(1);
    expect(findSavedPlace(input, 'p2')?.id).toBe('p2');
    expect(findSavedPlace(input, 'nope')).toBeUndefined();
  });
});

describe('makePlaceId', () => {
  it('produces a slug-based id', () => {
    expect(makePlaceId('custom', 'Dubai Mall')).toMatch(/^custom-dubai-mall-/);
  });

  it('falls back when name has no slug chars', () => {
    expect(makePlaceId('custom', '123')).toMatch(/^custom-123-/);
  });
});