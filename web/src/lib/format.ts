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
