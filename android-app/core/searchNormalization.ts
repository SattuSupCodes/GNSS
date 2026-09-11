import type { SearchResult } from '@/types/search';
import type { Coordinate } from '@/types/routing';

/**
 * Normalization of GraphHopper geocoding responses into SearchResult.
 * Pure; unit-tested against fixture JSON.
 */

export interface GraphHopperHit {
  osm_id?: number;
  name?: string;
  country?: string;
  city?: string;
  state?: string;
  street?: string;
  housenumber?: string;
  postcode?: string;
  osm_value?: string;
  point?: { lat: number; lng: number };
  extent?: number[];
}

export interface GraphHopperGeocodeResponse {
  hits?: GraphHopperHit[];
  locale?: string;
}

export const SEARCH_PROVIDER_LABEL = 'GraphHopper';

/** Compose a reasonably readable address string from available parts. */
export function composeAddress(hit: GraphHopperHit): string {
  const parts: string[] = [];
  if (hit.housenumber) parts.push(hit.housenumber);
  if (hit.street) parts.push(hit.street);
  const locality = hit.city ?? hit.state ?? hit.country;
  if (locality) parts.push(locality);
  return parts.filter(Boolean).join(', ');
}

function toCoordinate(hit: GraphHopperHit): Coordinate | null {
  if (hit.point && Number.isFinite(hit.point.lat) && Number.isFinite(hit.point.lng)) {
    return { latitude: hit.point.lat, longitude: hit.point.lng };
  }
  if (hit.extent && hit.extent.length >= 2) {
    return {
      latitude: hit.extent[1] + (hit.extent[3] - hit.extent[1]) / 2,
      longitude: hit.extent[0] + (hit.extent[2] - hit.extent[0]) / 2,
    };
  }
  return null;
}

export function normalizeGeocodeResponse(json: GraphHopperGeocodeResponse): SearchResult[] {
  const hits = json.hits ?? [];
  return hits.map((hit, index) => ({
    id: hit.osm_id !== undefined ? `gh-osm:${hit.osm_id}` : `gh-${index}`,
    name: hit.name || composeAddress(hit) || 'Unknown place',
    address: composeAddress(hit),
    position: toCoordinate(hit),
    category: hit.osm_value ?? null,
    sourceLabel: SEARCH_PROVIDER_LABEL,
  }));
}