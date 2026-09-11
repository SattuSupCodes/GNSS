import { useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { MetricCard, SensorRow, TelemetryChip } from '@/components/Metrics';
import { fonts, radius, spacing } from '@/constants/theme';
import { StatusBanner } from '@/components/StatusBanner';
import { useTheme } from '@/lib/theme';
import { isSensorAvailable } from '@/services/sensors/sensorManager';
import { useNavigationSession } from '@/state/NavigationProvider';
import type { SensorKind } from '@/types/sensor';
import { formatSpeedKmh } from '@/utils/format';

const SENSORS: { kind: SensorKind; name: string; icon: 'gyro' | 'motion' | 'magnetometer' }[] = [
  { kind: 'gyroscope', name: 'Gyroscope', icon: 'gyro' },
  { kind: 'accelerometer', name: 'Accelerometer', icon: 'motion' },
  { kind: 'magnetometer', name: 'Magnetometer', icon: 'magnetometer' },
];

const SOURCE_LABEL: Record<string, string> = {
  gnss: 'GNSS',
  hybrid: 'GNSS + IDR',
  idr: 'IDR',
  unknown: '—',
};

export default function DiagnosticsScreen() {
  const router = useRouter();
  const { theme } = useTheme();
  const { snapshot, demoMode } = useNavigationSession();
  const [sensors, setSensors] = useState<Record<SensorKind, boolean | null>>({
    gyroscope: null,
    accelerometer: null,
    magnetometer: null,
  });

  useEffect(() => {
    let mounted = true;
    for (const sensor of SENSORS) {
      isSensorAvailable(sensor.kind).then((available) => {
        if (mounted) {
          setSensors((prev) => ({ ...prev, [sensor.kind]: available }));
        }
      });
    }
    return () => {
      mounted = false;
    };
  }, []);

  const position = snapshot.position;
  const accuracy = position?.accuracy ?? null;
  const latitude = position?.latitude ?? null;
  const longitude = position?.longitude ?? null;

  return (
    <Screen>
      <View>
        <ScreenHeader title="Diagnostics" onBack={() => router.back()} variant="plain" right={<TelemetryChip label={demoMode ? 'DEMO' : 'LIVE'} value="" tone={demoMode ? 'demo' : 'ok'} />} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <StatusBanner status={snapshot.positioningStatus} />

        <View style={[styles.demoBanner, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
          <Text style={[styles.demoTag, { color: theme.colors.secondary, fontFamily: fonts.black, letterSpacing: 1 }]}>
            LIVE TELEMETRY
          </Text>
          <Text style={[styles.demoNote, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            Values come from the live GNSS provider. IDR and ML speed remain engineering-phase contracts.
          </Text>
        </View>

        <View style={[styles.constellation, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }]}>
          <Text style={[styles.constellationLabel, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Positioning technology
          </Text>
          <Text style={[styles.constellationValue, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
            GPS (GNSS)
          </Text>
          <Text style={[styles.constellationMode, { color: theme.colors.secondary, fontFamily: fonts.medium }]}>
            Source: {SOURCE_LABEL[snapshot.positionSource] ?? snapshot.positionSource} · Phase: {snapshot.phase}
          </Text>
        </View>

        <View style={styles.grid}>
          <MetricCard label="Latitude" value={latitude !== null ? latitude.toFixed(5) : '--'} tone="idle" icon="radar" />
          <MetricCard label="Longitude" value={longitude !== null ? longitude.toFixed(5) : '--'} tone="idle" icon="radar" />
          <MetricCard label="Horiz. accuracy" value={accuracy !== null ? accuracy.toFixed(1) : '--'} unit="m" tone={accuracy !== null && accuracy > 60 ? 'warn' : 'ok'} icon="radar" />
          <MetricCard label="Speed" value={formatSpeedKmh(snapshot.speedMps)} unit="km/h" tone="ok" icon="speed" />
          <MetricCard label="Heading" value={snapshot.headingDeg !== null ? `${Math.round(snapshot.headingDeg)}\u00b0` : '--'} tone="idle" icon="compass" />
          <MetricCard label="Position mode" value={SOURCE_LABEL[snapshot.positionSource] ?? '—'} tone="ok" icon="signal" />
        </View>

        <View style={styles.sensorGroup}>
          <Text style={[styles.sensorTitle, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.semibold }]}>
            SENSOR PIPELINE
          </Text>
          <GlassSurface variant="floating" style={styles.sensorCard}>
            {SENSORS.map((sensor) => {
              const available = sensors[sensor.kind];
              return (
                <SensorRow
                  key={sensor.kind}
                  icon={sensor.icon}
                  name={sensor.name}
                  state={available === null ? 'Checking' : available ? 'Available' : 'Unavailable'}
                  tone={available === null ? 'idle' : available ? 'ok' : 'warn'}
                />
              );
            })}
          </GlassSurface>
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: spacing.gutter,
    gap: spacing.lg,
    paddingBottom: spacing.xl,
  },
  demoBanner: {
    borderRadius: radius.lg,
    padding: spacing.md,
    gap: spacing.xs,
  },
  demoTag: {
    fontSize: 11,
    lineHeight: 15,
  },
  demoNote: {
    fontSize: 11,
    lineHeight: 16,
  },
  constellation: {
    borderRadius: radius.xl,
    padding: spacing.lg,
    borderWidth: StyleSheet.hairlineWidth,
  },
  constellationLabel: {
    fontSize: 11,
    lineHeight: 15,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  constellationValue: {
    fontSize: 20,
    lineHeight: 26,
    marginTop: spacing.xs,
  },
  constellationMode: {
    fontSize: 13,
    lineHeight: 18,
    marginTop: 2,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  sensorGroup: {
    gap: spacing.sm,
  },
  sensorTitle: {
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 0.6,
  },
  sensorCard: {
    borderRadius: radius.xl,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
  },
});