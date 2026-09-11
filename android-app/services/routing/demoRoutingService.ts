import { bearingDegrees, haversineDistanceMeters } from '@/core/geo';
import type { Coordinate, Maneuver, Route, RouteRequest, RouteResult } from '@/types/routing';

/**
 * DEMO-ONLY routing engine.
 *
 * Generates a plausible route (L-shaped polyline + depart/turn/arrive
 * maneuvers) so the navigation UI can be exercised with no network and no API
 * key. Everything it produces is synthetic; it is only ever selected from the
 * explicit "demo mode" toggle in the UI, never from the production path.
 */

export class DemoRoutingService {
  readonly id = 'demo-routing';
  readonly isDemo = true;

  async calculate(request: RouteRequest): Promise<RouteResult> {
    return {
      routes: [this.buildDemoRoute(request)],
      request,
      provider: 'demo',
    };
  }

  private buildDemoRoute(request: RouteRequest): Route {
    const { origin, destination } = request;

    // An L-shaped polyline (two hops) gives the demo a visible turn.
    const mid = {
      latitude: origin.latitude,
      longitude: destination.longitude,
    };
    const geometry: Coordinate[] = [origin, mid, destination];

    let total = 0;
    for (let i = 0; i < geometry.length - 1; i++) {
      total += haversineDistanceMeters(geometry[i], geometry[i + 1]);
    }

    const maneuvers: Maneuver[] = [
      {
        action: 'depart',
        instruction: 'Head to the route',
        approachDistanceMeters: 0,
        approachDurationSeconds: 0,
        coordinates: geometry.slice(0, 2),
      },
      {
        action: 'turn-right',
        instruction: 'Turn right at the demo junction',
        approachDistanceMeters: Math.round(total / 2),
        approachDurationSeconds: Math.round(total / 2 / 8),
        coordinates: geometry.slice(1),
      },
      {
        action: 'arrive',
        instruction: 'Arrive at destination',
        approachDistanceMeters: Math.round(total / 2),
        approachDurationSeconds: Math.round(total / 2 / 8),
        coordinates: geometry.slice(1),
      },
    ];

    const bearing = bearingDegrees(origin, destination);

    return {
      geometry,
      distanceMeters: Math.round(total),
      durationSeconds: Math.round(total / 8) + (bearing ? 0 : 0),
      maneuvers,
      bounds: null,
    };
  }
}

export const demoRoutingService = new DemoRoutingService();