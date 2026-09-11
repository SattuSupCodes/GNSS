import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useRouter } from 'expo-router';

import { GlassSurface } from '@/components/Glass';
import { ScreenHeader } from '@/components/Header';
import { Screen } from '@/components/Screen';
import { MetricCard, SensorRow, TelemetryChip } from '@/components/Metrics';
import { fonts, radius, spacing } from '@/constants/theme';
import { diagnosticsDemo, sensorDemo } from '@/constants/mockData';
import { useTheme } from '@/lib/theme';
import { StatusBanner } from '@/components/StatusBanner';

export default function DiagnosticsScreen() {
  const router = useRouter();
  const { theme } = useTheme();

  return (
    <Screen>
      <View>
        <ScreenHeader title="Diagnostics" onBack={() => router.back()} variant="plain" right={<TelemetryChip label="ISRO SIH 2026" value="" tone="demo" />} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <StatusBanner status="gnss-connected" />

        <View style={[styles.demoBanner, { backgroundColor: theme.colors.surfaceContainerHigh }]}>
          <Text style={[styles.demoTag, { color: theme.colors.secondary, fontFamily: fonts.black, letterSpacing: 1 }]}>
            {diagnosticsDemo.label}
          </Text>
          <Text style={[styles.demoNote, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.regular }]}>
            Illustrative values preview the UI layout only. Real values arrive with the sensor, GNSS and IDR pipelines.
          </Text>
        </View>

        <View style={[styles.constellation, { backgroundColor: theme.colors.glassFloating.fill, borderColor: theme.colors.glassFloating.border }]}>
          <Text style={[styles.constellationLabel, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.medium }]}>
            Positioning technology
          </Text>
          <Text style={[styles.constellationValue, { color: theme.colors.onSurface, fontFamily: fonts.semibold }]}>
            {diagnosticsDemo.constellation}
          </Text>
          <Text style={[styles.constellationMode, { color: theme.colors.secondary, fontFamily: fonts.medium }]}>
            {diagnosticsDemo.modeLabel}
          </Text>
        </View>

        <View style={styles.grid}>
          <MetricCard label="Filter confidence" value={diagnosticsDemo.confidence} tone="demo" icon="queryStats" />
          <MetricCard label="CEP50" value={diagnosticsDemo.cep50} tone="demo" icon="radar" />
          <MetricCard label="Horiz. accuracy" value={diagnosticsDemo.accuracy} tone="demo" icon="radar" />
          <MetricCard label="Satellites" value={diagnosticsDemo.satellites} tone="ok" icon="satellite" />
          <MetricCard label="Update rate" value={diagnosticsDemo.updateRate} tone="demo" icon="pulse" />
          <MetricCard label="Position mode" value="Fusion" tone="demo" icon="signal" />
        </View>

        <View style={styles.sensorGroup}>
          <Text style={[styles.sensorTitle, { color: theme.colors.onSurfaceVariant, fontFamily: fonts.semibold }]}>
            SENSOR PIPELINE
          </Text>
          <GlassSurface variant="floating" style={styles.sensorCard}>
            {sensorDemo.map((sensor) => (
              <SensorRow key={sensor.id} icon={sensor.icon} name={sensor.name} state={sensor.state} tone={sensor.tone} />
            ))}
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