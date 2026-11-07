const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function formatInt(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? "–" : integer.format(value);
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined || Number.isNaN(value)
    ? "–"
    : `${(value * 100).toFixed(digits)}%`;
}

export function formatAge(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "–";
  if (seconds < 90) return `${Math.round(seconds)} s`;
  return `${Math.round(seconds / 60)} min`;
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
}

export function formatHour(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short",
    hour: "numeric",
    timeZone: "America/New_York",
  });
}

/** Weekday and time to the minute in New York, e.g. "Sat 6:40 PM". */
export function formatDayTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
}

/** Whole seconds between an ISO time and now (never negative). */
export function secondsSince(iso: string, nowMs: number): number {
  return Math.max(0, Math.round((nowMs - new Date(iso).getTime()) / 1000));
}

/** "1 second ago", "45 seconds ago", "3 minutes ago". */
export function formatAgo(seconds: number): string {
  if (seconds < 120) return `${seconds} ${seconds === 1 ? "second" : "seconds"} ago`;
  return `${Math.round(seconds / 60)} minutes ago`;
}
