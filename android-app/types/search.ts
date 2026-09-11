import type { Coordinate } from '@/types/routing';

export interface SearchResult {
  /** Stable id, unique per provider. */
  id: string;
  name: string;
  address: string;
  position: Coordinate | null;
  category: string | null;
  /** Human-readable attribution for the source of this result. */
  sourceLabel: string;
}

export interface SearchOptions {
  limit?: number;
  /** Bias results toward this point (country/locale hints). */
  around?: Coordinate;
  signal?: AbortSignal;
}

export interface SearchProvider {
  readonly id: string;
  readonly isDemo: boolean;
  search(query: string, options?: SearchOptions): Promise<SearchResult[]>;
}