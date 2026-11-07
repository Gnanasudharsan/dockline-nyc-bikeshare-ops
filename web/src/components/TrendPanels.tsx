import { Chart } from "./Chart";
import { formatClock, formatInt, formatPercent } from "@/lib/format";
import type { DailyKpis, Finding, History24h, SeriesKey } from "@/lib/types";

type ChartSpec = NonNullable<Finding["chart"]>;

/** One point per hour, counting back from the newest 10-minute frame. */
function hourly<T>(values: T[]): T[] {
  return values.filter((_, index) => (values.length - 1 - index) % 6 === 0);
}

function shortDate(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

interface Panel {
  id: string;
  title: string;
  summary: string;
  chart: ChartSpec;
}

function panels(history: History24h, daily: DailyKpis | null): Panel[] {
  const hours = hourly(history.frames.map((frame) => formatClock(frame)));
  const series = (key: SeriesKey) => hourly(history.series[key]);
  const latest = (key: SeriesKey) => history.series[key].at(-1) ?? null;
  const result: Panel[] = [
    {
      id: "empty-full",
      title: "Empty and full stations",
      summary: `Now: ${formatInt(latest("empty_stations"))} empty, ${formatInt(latest("full_stations"))} full.`,
      chart: {
        kind: "line",
        categories: hours,
        series: [
          { name: "Empty (no bikes)", values: series("empty_stations"), color: "starving" },
          { name: "Full (no docks)", values: series("full_stations"), color: "flooding" },
        ],
        unit: "count",
      },
    },
    {
      id: "bikes-docks",
      title: "Bikes and docks available",
      summary: `Now: ${formatInt(latest("bikes_available"))} bikes and ${formatInt(latest("docks_available"))} free docks.`,
      chart: {
        kind: "line",
        categories: hours,
        series: [
          { name: "Bikes", values: series("bikes_available"), color: "signal" },
          { name: "Free docks", values: series("docks_available"), color: "slate" },
        ],
        unit: "bikes",
      },
    },
    {
      id: "fill",
      title: "Network fill ratio",
      summary: `Now: ${formatPercent(latest("fill_ratio"))} of usable slots hold a bike (target 50%).`,
      chart: {
        kind: "line",
        categories: hours,
        series: [{ name: "Fill ratio", values: series("fill_ratio"), color: "signal" }],
        unit: "percent",
      },
    },
  ];
  const days = (daily?.days ?? []).filter((day) => day.availability_rate !== null);
  if (days.length > 0) {
    result.push({
      id: "availability",
      title: "Availability rate by day",
      summary: `Share of sampled in-service stations with at least one bike and one dock; ${days.length} ${days.length === 1 ? "day" : "days"} so far.`,
      chart: {
        kind: "column",
        categories: days.map((day) => shortDate(day.date)),
        series: [
          {
            name: "Availability rate",
            values: days.map((day) => day.availability_rate),
            color: "signal",
          },
        ],
        unit: "percent",
      },
    });
  }
  return result;
}

/** Snapshot mode's stand-in for the Grafana dashboard: trends from the 24-hour history. */
export function TrendPanels({
  history,
  daily,
}: {
  history: History24h | null;
  daily: DailyKpis | null;
}) {
  return (
    <section aria-labelledby="trends-heading" className="mt-16">
      <h2 id="trends-heading" className="headline text-xl">
        Trends
      </h2>
      {!history || history.frames.length < 2 ? (
        <p className="mt-4 text-slate">
          {history
            ? "Not enough history yet: trends appear after two 10-minute snapshots."
            : "The snapshot history is unavailable right now. Try again in a few minutes."}
        </p>
      ) : (
        <>
          <p className="measure mt-2 text-slate">
            From snapshots taken every 10 minutes (last at {formatClock(history.generated_at)} New
            York time), shown hourly. The same certified definitions as the rest of Dockline.
          </p>
          <div className="mt-6 grid gap-12 lg:grid-cols-2 lg:gap-x-10">
            {panels(history, daily).map((panel) => (
              <section key={panel.id} aria-labelledby={`trend-${panel.id}`}>
                <h3 id={`trend-${panel.id}`} className="headline text-lg">
                  {panel.title}
                </h3>
                <p className="mt-1 text-sm text-slate">{panel.summary}</p>
                <div className="mt-3">
                  <Chart chart={panel.chart} title={`${panel.title}. ${panel.summary}`} />
                </div>
              </section>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
