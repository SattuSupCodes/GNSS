export function formatDuration(totalMinutes: number): string {
  if (totalMinutes < 60) {
    return `${Math.round(totalMinutes)} min`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = Math.round(totalMinutes % 60);
  return minutes === 0 ? `${hours} hr` : `${hours} hr ${minutes} min`;
}

export function formatClock(date: Date): string {
  const hours = date.getHours();
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const suffix = hours >= 12 ? 'PM' : 'AM';
  const hour12 = hours % 12 === 0 ? 12 : hours % 12;
  return `${hour12}:${minutes} ${suffix}`;
}

export function greeting(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) {
    return 'Good morning';
  }
  if (hour < 17) {
    return 'Good afternoon';
  }
  return 'Good evening';
}

export function formatMeters(meters: number | null): string {
  if (meters === null || Number.isNaN(meters)) return '--';
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

export function formatSpeedKmh(speedMps: number | null): string {
  if (speedMps === null || Number.isNaN(speedMps)) return '—';
  return String(Math.round(speedMps * 3.6));
}