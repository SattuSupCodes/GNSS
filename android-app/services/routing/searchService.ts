import { env, isGraphHopperConfigured } from '@/config/env';
import { normalizeGeocodeResponse, type GraphHopperGeocodeResponse } from '@/core/searchNormalization';
import type { SearchOptions, SearchProvider, SearchResult } from '@/types/search';

/**
 * Geocoding/search providers.
 *
 * GraphHopperSearchProvider uses the /geocode endpoint (nominatim-backed).
 * DemoSearchProvider is labeled demo and returns clearly fake results for
 * offline UI exercise.
 */

export class GraphHopperSearchProvider implements SearchProvider {
  readonly id = 'graphhopper';
  readonly isDemo = false;

  constructor(
    private readonly options: {
      apiUrl?: string;
      apiKey?: string;
      timeoutMs?: number;
      fetchImpl?: typeof fetch;
    } = {},
  ) {}

  async search(query: string, options?: SearchOptions): Promise<SearchResult[]> {
    const trimmed = query.trim();
    if (!trimmed) return [];

    const apiKey = this.options.apiKey ?? env.graphhopperApiKey;
    if (!apiKey) {
      throw new Error(
        'Search needs a GraphHopper API key. Add EXPO_PUBLIC_GRAPHHOPPER_API_KEY to your .env file.',
      );
    }

    const fetchImpl = this.options.fetchImpl ?? fetch;
    const base = (this.options.apiUrl ?? env.graphhopperApiUrl).replace(/\/$/, '');
    const queryParams: string[] = [];
    const push = (k: string, v: string) => queryParams.push(`${k}=${encodeURIComponent(v)}`);
    push('q', trimmed);
    push('limit', String(options?.limit ?? 7));
    push('locale', 'en');
    push('key', apiKey);
    if (options?.around) {
      push('point', `${options.around.latitude},${options.around.longitude}`);
    }
    const url = `${base}/geocode?${queryParams.join('&')}`;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.options.timeoutMs ?? 20_000);

    try {
      const response = await fetchImpl(url, { method: 'GET', signal: options?.signal ?? controller.signal });
      if (!response.ok) {
        throw new Error('Search request failed. Check your connection and try again.');
      }
      const json = (await response.json()) as GraphHopperGeocodeResponse;
      return normalizeGeocodeResponse(json);
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Search timed out.');
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
}

export const searchProvider: GraphHopperSearchProvider = new GraphHopperSearchProvider();

export function createSearchProvider(options?: {
  apiUrl?: string;
  apiKey?: string;
  fetchImpl?: typeof fetch;
}): GraphHopperSearchProvider {
  return new GraphHopperSearchProvider(options);
}

export function isSearchConfigured(): boolean {
  return isGraphHopperConfigured();
}