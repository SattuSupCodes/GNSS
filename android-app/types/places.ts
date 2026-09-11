import type { Coordinate } from '@/types/routing';

export type SavedPlaceKind = 'home' | 'work' | 'favorite';

export interface SavedPlace {
  id: string;
  kind: SavedPlaceKind;
  name: string;
  address: string;
  position: Coordinate;
  createdAt: number;
}

export interface RecentSearch {
  id: string;
  query: string;
  name: string;
  position: Coordinate | null;
  searchedAt: number;
}