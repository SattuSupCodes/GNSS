import type { SearchOptions, SearchProvider, SearchResult } from '@/types/search';

/**
 * DEMO-ONLY search provider.
 *
 * Returns clearly-labeled sample places so the search UI can be exercised
 * offline. Never used from the production path.
 */

const DEMO_PLACES: Array<Pick<SearchResult, 'name' | 'address' | 'position' | 'category'>> = [
  { name: 'Jumeirah Beach Residence', address: 'Dubai Marina, Dubai', position: { latitude: 25.0782, longitude: 55.1321 }, category: 'leisure' },
  { name: 'Dubai Marina Mall', address: 'Dubai Marina, Dubai', position: { latitude: 25.0801, longitude: 55.1391 }, category: 'shopping' },
  { name: 'Burj Khalifa', address: 'Downtown Dubai, Dubai', position: { latitude: 25.1972, longitude: 55.2744 }, category: 'landmark' },
  { name: 'Palm Jumeirah Monorail Station', address: 'Palm Jumeirah, Dubai', position: { latitude: 25.1124, longitude: 55.1393 }, category: 'transit' },
  { name: 'Dubai International Airport (DXB)', address: 'Al Garhoud, Dubai', position: { latitude: 25.2532, longitude: 55.3657 }, category: 'airport' },
];

export class DemoSearchProvider implements SearchProvider {
  readonly id = 'demo-search';
  readonly isDemo = true;

  async search(query: string, options?: SearchOptions): Promise<SearchResult[]> {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    const limit = options?.limit ?? 6;
    return DEMO_PLACES.filter(
      (p) => p.name.toLowerCase().includes(q) || p.address.toLowerCase().includes(q),
    )
      .slice(0, limit)
      .map((p, i) => ({
        id: `demo:${i}:${p.name}`,
        name: p.name,
        address: p.address,
        position: p.position,
        category: p.category ?? null,
        sourceLabel: 'Demo',
      }));
  }
}

export const demoSearchProvider = new DemoSearchProvider();