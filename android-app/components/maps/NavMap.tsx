import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from 'react';
import { StyleSheet } from 'react-native';
import {
  Camera,
  CameraRef,
  GeoJSONSource,
  Layer,
  Map,
  Marker,
  type LngLatBounds,
} from '@maplibre/maplibre-react-native';
import { resolveMapStyle } from '@/config/map';
import { Waypoint, PulseMarker } from '@/components/MapAnnotations';
import type { Coordinate } from '@/types/routing';
import type { GeoPosition } from '@/types/position';

/**
 * Navigation map — MapLibre native.
 *
 * Renders the route polyline (glow + main), origin/destination markers, and
 * the live user position marker. Camera behavior is driven by the parent:
 * `followUser` keeps the view glued to the fix; user-initiated pan/zoom/rotate
 * fires `onUserInteraction` so screens can drop follow mode and show the
 * "recenter" control.
 */

export interface NavMapHandle {
  fitRoute(): void;
}

export interface NavMapProps {
  styleId: string;
  /** Route polyline (origin → destination), or null when only browsing. */
  coords: Coordinate[] | null;
  origin: Coordinate | null;
  destination: Coordinate | null;
  userPosition: GeoPosition | null;
  followUser: boolean;
  /** When true, camera fits the route whenever a fresh route is provided. */
  fitRouteOnChange?: boolean;
  onUserInteraction?: () => void;
}

const FALLBACK_LNG_LAT: [number, number] = [55.14, 25.07];

function toLngLat(c: Coordinate | null): [number, number] {
  return c ? [c.longitude, c.latitude] : FALLBACK_LNG_LAT;
}

function routeBounds(coords: Coordinate[]): LngLatBounds | null {
  if (coords.length === 0) return null;
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;
  for (const c of coords) {
    if (c.longitude < minLng) minLng = c.longitude;
    if (c.longitude > maxLng) maxLng = c.longitude;
    if (c.latitude < minLat) minLat = c.latitude;
    if (c.latitude > maxLat) maxLat = c.latitude;
  }
  return [minLng, minLat, maxLng, maxLat] as LngLatBounds;
}

export const NavMap = forwardRef<NavMapHandle, NavMapProps>(function NavMap(
  { styleId, coords, origin, destination, userPosition, followUser, fitRouteOnChange = true, onUserInteraction },
  ref,
) {
  const camera = useRef<CameraRef>(null);
  const mapStyle = useMemo(() => resolveMapStyle(styleId), [styleId]);

  const lineSource = useMemo(() => {
    if (!coords || coords.length < 2) return null;
    return {
      type: 'FeatureCollection' as const,
      features: [
        {
          type: 'Feature' as const,
          properties: {},
          geometry: {
            type: 'LineString' as const,
            coordinates: coords.map((c) => [c.longitude, c.latitude]),
          },
        },
      ],
    };
  }, [coords]);

  // Fit the route once when it appears/changes.
  const fittedRouteRef = useRef<string | null>(null);
  const routeKey = coords ? coords.map((c) => `${c.longitude.toFixed(5)},${c.latitude.toFixed(5)}`).join('|') : null;
  useEffect(() => {
    if (!coords || !fitRouteOnChange || !routeKey) return;
    if (fittedRouteRef.current === routeKey) return;
    fittedRouteRef.current = routeKey;
    const bounds = routeBounds(coords);
    if (bounds && camera.current) {
      camera.current.fitBounds(bounds, { padding: { top: 90, right: 40, bottom: 90, left: 40 }, duration: 700 });
    }
  }, [routeKey, coords, fitRouteOnChange]);

  // Follow the user position.
  const lastFollowKey = useRef<string | null>(null);
  useEffect(() => {
    if (!followUser || !userPosition) return;
    const key = `${userPosition.longitude.toFixed(6)},${userPosition.latitude.toFixed(6)}`;
    if (lastFollowKey.current === key) return;
    lastFollowKey.current = key;
    if (!camera.current) return;
    camera.current.easeTo({
      center: [userPosition.longitude, userPosition.latitude],
      zoom: 16,
      duration: 350,
    });
  }, [followUser, userPosition]);

  useImperativeHandle(
    ref,
    () => ({
      fitRoute() {
        const bounds = coords ? routeBounds(coords) : null;
        if (bounds && camera.current) {
          camera.current.fitBounds(bounds, { padding: { top: 90, right: 40, bottom: 90, left: 40 }, duration: 600 });
        } else if (camera.current) {
          camera.current.flyTo({ center: toLngLat(userPosition ?? destination ?? origin), zoom: 15, duration: 600 });
        }
      },
    }),
    [coords, userPosition, destination, origin],
  );

  return (
    <Map
      style={StyleSheet.absoluteFill}
      mapStyle={mapStyle}
      compass={false}
      logo
      attribution
      scaleBar={false}
      onRegionWillChange={(event) => {
        if (event?.nativeEvent?.userInteraction) {
          onUserInteraction?.();
        }
      }}
    >
      <Camera
        ref={camera}
        initialViewState={{
          center: toLngLat(userPosition ?? destination ?? origin),
          zoom: 14,
        }}
      />

      {lineSource ? (
        <GeoJSONSource id="nav-route" data={lineSource}>
          <Layer
            id="nav-route-glow"
            type="line"
            source="nav-route"
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            paint={{
              'line-color': '#3EC5FF',
              'line-width': 9,
              'line-opacity': 0.35,
            }}
          />
          <Layer
            id="nav-route-main"
            type="line"
            source="nav-route"
            layout={{ 'line-cap': 'round', 'line-join': 'round' }}
            paint={{
              'line-color': '#0B7AFB',
              'line-width': 4.5,
              'line-opacity': 0.95,
            }}
          />
        </GeoJSONSource>
      ) : null}

      {destination ? (
        <Marker id="nav-destination" lngLat={toLngLat(destination)} anchor="center" offset={[0, -16]}>
          <Waypoint label="Dest" />
        </Marker>
      ) : null}

      {origin && !coords ? (
        <Marker id="nav-origin" lngLat={toLngLat(origin)} anchor="center">
          <Waypoint label="Start" icon="locationPin" color="#0B7AFB" size={22} />
        </Marker>
      ) : null}

      {userPosition ? (
        <Marker id="nav-user" lngLat={[userPosition.longitude, userPosition.latitude]} anchor="center">
          <PulseMarker size={24} color="#0B7AFB" />
        </Marker>
      ) : null}
    </Map>
  );
});