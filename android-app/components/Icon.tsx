import { MaterialCommunityIcons, MaterialIcons } from '@expo/vector-icons';

import { useTheme } from '@/lib/theme';

type MIKey = keyof typeof MaterialIcons.glyphMap;
type MCIKey = keyof typeof MaterialCommunityIcons.glyphMap;

const MI = 'MaterialIcons';
const MCI = 'MaterialCommunityIcons';

/**
 * Canonical icon registry. Every Stitch-screen glyph maps to a verified
 * @expo/vector-icons name so screens never reference missing glyphs.
 */
const iconMap = {
  search: { set: MI, name: 'search' },
  mic: { set: MI, name: 'mic' },
  account: { set: MCI, name: 'account' },
  accountCircle: { set: MCI, name: 'account-circle' },
  home: { set: MI, name: 'home' },
  work: { set: MI, name: 'work' },
  restaurant: { set: MI, name: 'restaurant' },
  fuel: { set: MI, name: 'local-gas-station' },
  parking: { set: MI, name: 'local-parking' },
  coffee: { set: MI, name: 'local-cafe' },
  car: { set: MI, name: 'directions-car' },
  transit: { set: MI, name: 'directions-transit' },
  walk: { set: MI, name: 'directions-walk' },
  bike: { set: MI, name: 'directions-bike' },
  explore: { set: MI, name: 'explore' },
  route: { set: MI, name: 'route' },
  saved: { set: MI, name: 'bookmark' },
  savedOutline: { set: MI, name: 'bookmark-border' },
  profile: { set: MI, name: 'person-outline' },
  compass: { set: MCI, name: 'compass-outline' },
  layers: { set: MI, name: 'layers' },
  recenter: { set: MI, name: 'my-location' },
  back: { set: MI, name: 'arrow-back' },
  forward: { set: MI, name: 'arrow-forward' },
  close: { set: MI, name: 'close' },
  chevronRight: { set: MI, name: 'chevron-right' },
  chevronLeft: { set: MI, name: 'chevron-left' },
  more: { set: MI, name: 'more-vert' },
  tune: { set: MI, name: 'tune' },
  settings: { set: MI, name: 'settings' },
  volume: { set: MI, name: 'volume-up' },
  mute: { set: MI, name: 'volume-mute' },
  info: { set: MI, name: 'info' },
  help: { set: MI, name: 'help' },
  history: { set: MI, name: 'history' },
  clock: { set: MCI, name: 'clock-outline' },
  download: { set: MI, name: 'download' },
  share: { set: MI, name: 'share' },
  arrowUp: { set: MI, name: 'arrow-upward' },
  arrowDown: { set: MI, name: 'arrow-downward' },
  turnLeft: { set: MI, name: 'turn-left' },
  turnRight: { set: MI, name: 'turn-right' },
  straight: { set: MI, name: 'arrow-upward' },
  forkLeft: { set: MI, name: 'fork-left' },
  forkRight: { set: MI, name: 'fork-right' },
  destination: { set: MCI, name: 'map-marker' },
  locationPin: { set: MI, name: 'location-on' },
  speed: { set: MI, name: 'speed' },
  gauge: { set: MCI, name: 'speedometer' },
  satellite: { set: MI, name: 'satellite' },
  gps: { set: MI, name: 'gps-fixed' },
  gpsOff: { set: MI, name: 'gps-off' },
  radar: { set: MI, name: 'radar' },
  queryStats: { set: MI, name: 'query-stats' },
  diagnostics: { set: MCI, name: 'chart-line' },
  gyro: { set: MCI, name: 'sine-wave' },
  motion: { set: MCI, name: 'motion-outline' },
  magnetometer: { set: MCI, name: 'compass' },
  altimeter: { set: MCI, name: 'speedometer' },
  brain: { set: MCI, name: 'brain' },
  flask: { set: MCI, name: 'flask' },
  headsUp: { set: MCI, name: 'head-heart-outline' },
  shield: { set: MCI, name: 'shield-check' },
  themeAuto: { set: MI, name: 'brightness-6' },
  themeLight: { set: MI, name: 'light-mode' },
  themeDark: { set: MI, name: 'dark-mode' },
  plus: { set: MI, name: 'add' },
  minus: { set: MI, name: 'remove' },
  check: { set: MI, name: 'check' },
  checkCircle: { set: MI, name: 'check-circle' },
  warning: { set: MI, name: 'warning' },
  alert: { set: MCI, name: 'alert-circle' },
  offline: { set: MI, name: 'cloud' },
  signal: { set: MCI, name: 'signal' },
  signalOff: { set: MCI, name: 'signal-off' },
  translate: { set: MI, name: 'translate' },
  logout: { set: MI, name: 'logout' },
  star: { set: MI, name: 'star' },
  starOutline: { set: MI, name: 'star-outline' },
  flight: { set: MI, name: 'flight-takeoff' },
  toll: { set: MI, name: 'toll' },
  traffic: { set: MI, name: 'traffic' },
  grid: { set: MCI, name: 'view-grid' },
  list: { set: MCI, name: 'view-list' },
  map: { set: MI, name: 'map' },
  pulse: { set: MCI, name: 'pulse' },
} as const;

export type IconName = keyof typeof iconMap;

interface IconProps {
  name: IconName;
  size?: number;
  color?: string;
}

export function Icon({ name, size = 22, color }: IconProps) {
  const { theme } = useTheme();
  const token = iconMap[name];
  const Color = color ?? theme.colors.onSurfaceVariant;
  if (token.set === MI) {
    return <MaterialIcons name={token.name as MIKey} size={size} color={Color} />;
  }
  return <MaterialCommunityIcons name={token.name as MCIKey} size={size} color={Color} />;
}