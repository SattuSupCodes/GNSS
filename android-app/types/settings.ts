export type AppearanceMode = 'system' | 'light' | 'dark';

export interface MapSettings {
  styleId: string;
  followUser: boolean;
  showScaleBar: boolean;
}

export interface NavigationSettings {
  rerouteEnabled: boolean;
  /** Perpendicular deviation (meters) beyond which the route is considered off. */
  rerouteThresholdMeters: number;
  /** Minimum seconds between automatic reroute attempts. */
  rerouteCooldownSeconds: number;
  /** Distance (meters) at which the destination counts as reached. */
  arrivalThresholdMeters: number;
}

export interface PrivacySettings {
  /** Whether anonymous pings may be shared with the routing provider. */
  shareAnalytics: boolean;
}

export interface AppSettings {
  map: MapSettings;
  navigation: NavigationSettings;
  privacy: PrivacySettings;
}

export const DEFAULT_SETTINGS: AppSettings = {
  map: {
    styleId: 'liberty',
    followUser: true,
    showScaleBar: false,
  },
  navigation: {
    rerouteEnabled: true,
    rerouteThresholdMeters: 60,
    rerouteCooldownSeconds: 30,
    arrivalThresholdMeters: 25,
  },
  privacy: {
    shareAnalytics: false,
  },
};