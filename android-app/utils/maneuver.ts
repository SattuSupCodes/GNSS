import type { IconName } from '@/components/Icon';
import type { ManeuverAction } from '@/types/routing';

/**
 * Maps routing-engine maneuver actions to the Stitch icon set.
 */
const ACTION_ICON: Record<ManeuverAction, IconName> = {
  depart: 'straight',
  arrive: 'destination',
  'turn-left': 'turnLeft',
  'turn-right': 'turnRight',
  'turn-slight-left': 'turnLeft',
  'turn-slight-right': 'turnRight',
  'turn-sharp-left': 'turnLeft',
  'turn-sharp-right': 'turnRight',
  straight: 'straight',
  uturn: 'turnLeft',
  'roundabout-right': 'forkRight',
  'keep-left': 'forkLeft',
  'keep-right': 'forkRight',
};

export function iconForAction(action: ManeuverAction): IconName {
  return ACTION_ICON[action];
}