import type { StyleSpecification } from '@maplibre/maplibre-react-native';

/**
 * Map style catalogue.
 *
 * Vector styles come from OpenFreeMap (free, no API key required):
 *   https://tiles.openfreemap.org/styles/{liberty,bright,positron,dark,fiord}
 * Satellite imagery uses the public Esri World Imagery raster tileset and is
 * provided inlined here so the app never depends on a proprietary key.
 */

export type MapStyleId =
  | 'liberty'
  | 'bright'
  | 'positron'
  | 'dark'
  | 'fiord'
  | 'satellite';

export interface MapStyleEntry {
  id: MapStyleId;
  label: string;
  appearance: 'light' | 'dark' | 'hybrid';
  /** Roughly how map labels render. */
  previewHint: string;
}

export const MAP_STYLES: MapStyleEntry[] = [
  { id: 'liberty', label: 'Liberty', appearance: 'light', previewHint: 'Colorful street map' },
  { id: 'bright', label: 'Bright', appearance: 'light', previewHint: 'High-contrast street map' },
  { id: 'positron', label: 'Positron', appearance: 'light', previewHint: 'Clean minimal light map' },
  { id: 'fiord', label: 'Fiord', appearance: 'dark', previewHint: 'Calm dark street map' },
  { id: 'dark', label: 'Dark', appearance: 'dark', previewHint: 'Near-black dark map' },
  { id: 'satellite', label: 'Satellite', appearance: 'hybrid', previewHint: 'Satellite imagery' },
];

export function isVectorStyleId(id: string): id is Exclude<MapStyleId, 'satellite'> {
  return id !== 'satellite';
}

/** Vector style URL for the given id, or null when the id is not a vector style. */
export function vectorStyleUrl(id: string): string | null {
  if (!isVectorStyleId(id)) {
    return null;
  }
  return `https://tiles.openfreemap.org/styles/${id}`;
}

const ESRI_WORLD_IMAGERY_TILES = [
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
];

const ESRI_ATTRIBUTION = 'Esri, Maxar, Earthstar Geographics';

function satelliteStyleSpecification(): StyleSpecification {
  return {
    version: 8,
    sources: {
      satellite: {
        type: 'raster',
        tiles: ESRI_WORLD_IMAGERY_TILES,
        tileSize: 256,
        attribution: ESRI_ATTRIBUTION,
      },
    },
    layers: [
      {
        id: 'satellite',
        type: 'raster',
        source: 'satellite',
      },
    ],
  };
}

/**
 * Resolve a style id into something MapLibre accepts: a remote style URL for
 * vector styles, or an inline StyleSpecification for raster satellite tiles.
 */
export function resolveMapStyle(id: string): string | StyleSpecification {
  const url = vectorStyleUrl(id);
  return url ?? satelliteStyleSpecification();
}