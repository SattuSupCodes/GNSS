import { forwardRef, useImperativeHandle, useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { MapCanvas } from '@/components/MapCanvas';
import { RouteLine, Waypoint } from '@/components/MapAnnotations';
import { fonts } from '@/constants/theme';
import { useTheme } from '@/lib/theme';
import type { Coordinate } from '@/types/routing';
import type { GeoPosition } from '@/types/position';
import type { NavMapHandle, NavMapProps } from './NavMap';

/**
 * Web fallback map.
 *
 * MapLibre Native only runs in the mobile app. For the web export we render
 * the stylized canvas with the route projected onto it (clearly a preview).
 */

type Rect = { minLng: number; minLat: number; maxLng: number; maxLat: number };

function fit(coords: Coordinate[], w: number, h: number, padding = 40) {
  const rect: Rect = {
    minLng: Math.min(...coords.map((c) => c.longitude)),
    maxLng: Math.max(...coords.map((c) => c.longitude)),
    minLat: Math.min(...coords.map((c) => c.latitude)),
    maxLat: Math.max(...coords.map((c) => c.latitude)),
  };
  if (rect.minLng === rect.maxLng && rect.minLat === rect.maxLat) {
    return coords.map(() => ({ x: w / 2, y: h / 2 }));
  }
  const usableW = w - padding * 2;
  const usableH = h - padding * 2;
  const scale = Math.min(usableW / (rect.maxLng - rect.minLng), usableH / (rect.maxLat - rect.minLat));
  return coords.map((c) => ({
    x: padding + (c.longitude - rect.minLng) * scale,
    y: padding + (rect.maxLat - c.latitude) * scale,
  }));
}

export const NavMap = forwardRef<NavMapHandle, NavMapProps>(function NavMap(
  { styleId: _styleId, coords, destination, origin, userPosition, followUser: _followUser, fitRouteOnChange: _fitRouteOnChange, onUserInteraction: _onUserInteraction },
  ref,
) {
  const { theme } = useTheme();
  const dark = theme.mode === 'dark';

  const project = useMemo(() => {
    const points = coords ?? (origin && destination ? [origin, destination] : destination ? [destination] : []);
    if (points.length < 2) return null;
    return fit(points, 360, 640);
  }, [coords, origin, destination]);

  useImperativeHandle(ref, () => ({ fitRoute: () => {} }), []);

  const linePoints = project ? project.map((p) => `${p.x},${p.y}`).join(' ') : null;

  const marker = destination && project ? project[project.length - 1] : null;
  const isBrowsing = !coords && (origin || destination || userPosition);

  return (
    <MapCanvas backdrop={coords ? 'route' : 'aerial'} style={StyleSheet.absoluteFill}>
      {linePoints ? (
        <View style={StyleSheet.absoluteFill} pointerEvents="none">
          <RouteLine points={linePoints} />
        </View>
      ) : null}

      {marker ? (
        <View
          pointerEvents="none"
          style={[styles.marker, { left: marker.x - 16, top: marker.y - 30 }]}
        >
          <Waypoint label="Dest" />
        </View>
      ) : null}

      {isBrowsing && !marker ? (
        <View style={[styles.marker, { right: 24, bottom: 120 }]} pointerEvents="none">
          <Waypoint label="You" icon="locationPin" color="#0B7AFB" />
        </View>
      ) : null}

      <View style={[styles.banner, { backgroundColor: dark ? 'rgba(6,12,20,0.72)' : 'rgba(255,255,255,0.82)' }]} pointerEvents="none">
        <Text style={[styles.bannerText, { color: theme.colors.onSurface, fontFamily: fonts.medium }]}>
          Web preview — the full live map runs in the mobile app
        </Text>
      </View>
    </MapCanvas>
  );
});

const styles = StyleSheet.create({
  marker: {
    position: 'absolute',
  },
  banner: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 16,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  bannerText: {
    fontSize: 12,
    lineHeight: 16,
    textAlign: 'center',
  },
});