import { composeAddress, normalizeGeocodeResponse } from '@/core/searchNormalization';

describe('composeAddress', () => {
  it('joins address parts', () => {
    expect(composeAddress({ housenumber: '12', street: 'Main St', city: 'Dubai' })).toBe('12, Main St, Dubai');
  });

  it('returns empty string when nothing present', () => {
    expect(composeAddress({})).toBe('');
  });
});

describe('normalizeGeocodeResponse', () => {
  it('maps hits with point coordinates', () => {
    const json = {
      hits: [{ osm_id: 100, name: 'Burj Khalifa', country: 'AE', city: 'Dubai', point: { lat: 25.19, lng: 55.27 } }],
    };
    const results = normalizeGeocodeResponse(json);
    expect(results).toHaveLength(1);
    expect(results[0].name).toBe('Burj Khalifa');
    expect(results[0].position).toEqual({ latitude: 25.19, longitude: 55.27 });
    expect(results[0].sourceLabel).toBe('GraphHopper');
  });

  it('falls back to address as the name', () => {
    const json = { hits: [{ housenumber: '5', street: 'Al Saada St' }] };
    const results = normalizeGeocodeResponse(json);
    expect(results[0].name).toBe('5, Al Saada St');
  });

  it('derives position from extent when point missing', () => {
    const json = { hits: [{ name: 'Area', extent: [55.0, 25.0, 55.2, 25.2] }] };
    const results = normalizeGeocodeResponse(json);
    expect(results[0].position).toEqual({ latitude: 25.1, longitude: 55.1 });
  });

  it('skips to a placeholder id when osm_id missing', () => {
    const json = { hits: [{ name: 'X' }] };
    const results = normalizeGeocodeResponse(json);
    expect(results[0].id).toBeDefined();
  });

  it('handles empty hits', () => {
    expect(normalizeGeocodeResponse({ hits: [] })).toEqual([]);
    expect(normalizeGeocodeResponse({})).toEqual([]);
  });

  it('does not fabricate a position when none exists', () => {
    const json = { hits: [{ name: 'Nowhere' }] };
    const results = normalizeGeocodeResponse(json);
    expect(results[0].position).toBeNull();
  });
});