import type {
  GeoPosition,
  PermissionState,
  PositionChangeListener,
  PositionProvider,
  PositioningStatus,
} from '@/types/position';

/**
 * Hybrid position provider — picks the most authoritative available source.
 *
 * Today GNSS is the only real provider. IDR/hybrid fusion is a future
 * contract (services/position/idrPositionProvider.ts): when it becomes
 * available, the providers array grows and the authority computation below
 * selects the best source per fix without further UI changes.
 *
 * Authority order: available > degraded > recovering > lost.
 */

const STATUS_RANK: Record<PositioningStatus, number> = {
  available: 4,
  degraded: 3,
  recovering: 2,
  lost: 1,
};

function rank(status: PositioningStatus): number {
  return STATUS_RANK[status] ?? 0;
}

export class HybridPositionProvider implements PositionProvider {
  readonly providerId = 'hybrid';
  readonly source = 'hybrid' as const;

  private readonly listeners = new Set<PositionChangeListener>();
  private readonly unsubscribes: (() => void)[] = [];
  private primary: PositionProvider | null = null;

  constructor(private readonly providers: PositionProvider[]) {}

  private get strongest(): PositionProvider | null {
    let best: PositionProvider | null = null;
    for (const provider of this.providers) {
      const score = rank(provider.getStatus());
      if (!best || score > rank(best.getStatus())) {
        best = provider;
      } else if (best && score === rank(best.getStatus())) {
        // Ties prefer the more precise provider — GNSS is the finest source.
        if (provider.providerId === 'gnss' && best.providerId !== 'gnss') {
          best = provider;
        }
      }
    }
    return best;
  }

  getStatus(): PositioningStatus {
    return this.strongest?.getStatus() ?? 'lost';
  }

  getCurrentPosition(): GeoPosition | null {
    const strongest = this.strongest;
    const direct = strongest?.getCurrentPosition() ?? null;
    if (direct) return direct;
    // Even when the strongest provider is currently "lost", surface the most
    // recent known fix so the map keeps showing the last true position.
    for (const provider of this.providers) {
      const position = provider.getCurrentPosition();
      if (position) return position;
    }
    return null;
  }

  getPermissionState(): PermissionState {
    const gnss = this.providers.find((p) => p.providerId === 'gnss');
    return gnss?.getPermissionState() ?? 'unavailable';
  }

  requestPermission(): Promise<PermissionState> {
    const gnss = this.providers.find((p) => p.providerId === 'gnss');
    return gnss?.requestPermission() ?? Promise.resolve('unavailable');
  }

  subscribe(listener: PositionChangeListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  async start(): Promise<void> {
    for (const provider of this.providers) {
      const unsubscribe = provider.subscribe(() => {
        if (this.primary !== this.strongest) {
          this.primary = this.strongest;
        }
        this.emit();
      });
      this.unsubscribes.push(unsubscribe);
      await provider.start();
    }
    this.primary = this.strongest;
  }

  stop(): void {
    for (const propagate of this.unsubscribes) propagate();
    this.unsubscribes.length = 0;
    for (const provider of this.providers) provider.stop();
    this.primary = null;
  }

  /** Providers exposed for diagnostics screens. */
  getProviders(): PositionProvider[] {
    return this.providers;
  }

  private emit(): void {
    const position = this.getCurrentPosition();
    for (const listener of this.listeners) {
      listener(position);
    }
  }
}