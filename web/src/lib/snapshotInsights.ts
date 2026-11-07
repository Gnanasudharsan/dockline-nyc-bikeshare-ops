// Insights for snapshot mode, built from the workflow's history files and the live
// feed. They only arrange certified metric values (docs/metrics.md); no new formulas.

import { formatClock, formatInt, formatPercent } from "./format";
import { getDailyKpis, getHistory, getLive } from "./snapshot";
import type { DailyKpis, Finding, History24h, InsightsResponse, LiveKpis } from "./types";

const FRAMES_PER_HOUR = 6;

/** Every 6th frame counting back from the newest: one point per hour. */
function hourly<T>(values: T[]): T[] {
  return values.filter((_, index) => (values.length - 1 - index) % FRAMES_PER_HOUR === 0);
}

function shortDate(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function emptyThroughTheDay(history: History24h | null): Finding {
  const frames = history?.frames ?? [];
  const empty = history?.series.empty_stations ?? [];
  const full = history?.series.full_stations ?? [];
  const enough = frames.length >= 2 * FRAMES_PER_HOUR;
  let peak = -1;
  empty.forEach((value, index) => {
    if (value !== null && (peak < 0 || value > (empty[peak] ?? -1))) peak = index;
  });
  const hours = hourly(frames.map((frame) => formatClock(frame)));
  return {
    id: "empty-through-the-day",
    title: "When stations run out of bikes",
    finding:
      enough && peak >= 0
        ? `In the last ${Math.round(frames.length / FRAMES_PER_HOUR)} hours, empty stations peaked at ${formatInt(empty[peak])} around ${formatClock(frames[peak] ?? "")} New York time; the latest count is ${formatInt(empty.at(-1))}.`
        : "Not enough history yet: the snapshot workflow needs about two hours of 10-minute samples.",
    recommendation: enough
      ? "Stage bikes at the stations that empty first, an hour before the peak, instead of chasing empties after it."
      : "Check back in a couple of hours; the history fills in every 10 minutes.",
    enough_data: enough,
    basis: `${formatInt(frames.length)} snapshots, one every 10 minutes (empty and full stations, docs/metrics.md)`,
    chart: enough
      ? {
          kind: "line",
          categories: hours,
          series: [
            { name: "Empty stations (no bikes)", values: hourly(empty), color: "starving" },
            { name: "Full stations (no docks)", values: hourly(full), color: "flooding" },
          ],
          unit: "count",
        }
      : null,
  };
}

function workRightNow(kpis: LiveKpis | null): Finding {
  return {
    id: "rebalancing-concentration",
    title: "Where the rebalancing work is right now",
    finding: kpis
      ? `${formatInt(kpis.starving_stations)} stations are starving and ${formatInt(kpis.flooding_stations)} are flooding. Bringing every one of them to half full means moving ${formatInt(kpis.rebalance_need_bikes)} bikes.`
      : "The live feed did not answer, so the current state is unknown.",
    recommendation: kpis
      ? "Pair trips: load bikes at flooding stations and drop them at nearby starving ones, so each truck run fixes two stations."
      : "Try again in a minute.",
    enough_data: kpis !== null,
    basis: kpis
      ? `the live feed at ${formatClock(kpis.as_of)} New York time (imbalance state and rebalancing need)`
      : "the live feed",
    chart: kpis
      ? {
          kind: "column",
          categories: ["Starving", "Balanced", "Flooding", "Offline"],
          series: [
            {
              name: "Stations",
              values: [
                kpis.starving_stations,
                kpis.balanced_stations,
                kpis.flooding_stations,
                kpis.offline_stations,
              ],
              color: "signal",
            },
          ],
          unit: "count",
        }
      : null,
  };
}

function availabilityByDay(daily: DailyKpis | null): Finding {
  const days = (daily?.days ?? []).filter((day) => day.availability_rate !== null);
  const enough = days.length >= 2;
  const best = [...days].sort((a, b) => (b.availability_rate ?? 0) - (a.availability_rate ?? 0))[0];
  const worst = [...days].sort(
    (a, b) => (a.availability_rate ?? 0) - (b.availability_rate ?? 0),
  )[0];
  return {
    id: "availability-by-day",
    title: "Availability, day by day",
    finding:
      enough && best && worst
        ? `Across ${days.length} days, availability ranged from ${formatPercent(worst.availability_rate)} (${shortDate(worst.date)}) to ${formatPercent(best.availability_rate)} (${shortDate(best.date)}).`
        : `Not enough history yet: day-by-day availability needs at least two days of snapshots${days[0] ? `; today so far it is ${formatPercent(days[0].availability_rate)}` : ""}.`,
    recommendation: enough
      ? "Compare the worst day's weather and weekday with the best; repeated patterns are where standing rebalancing plans pay off."
      : "Check back tomorrow.",
    enough_data: enough,
    basis:
      "sampled station states every 10 minutes (availability rate = available ÷ in-service station samples)",
    chart: enough
      ? {
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
        }
      : null,
  };
}

function ebikesThroughTheDay(history: History24h | null): Finding {
  const frames = history?.frames ?? [];
  const enough = frames.length >= 2 * FRAMES_PER_HOUR;
  const bikes = history?.series.bikes_available ?? [];
  const ebikes = history?.series.ebikes_available ?? [];
  const latestBikes = bikes.at(-1) ?? null;
  const latestEbikes = ebikes.at(-1) ?? null;
  return {
    id: "ebikes",
    title: "E-bikes in the available fleet",
    finding:
      latestBikes && latestEbikes !== null
        ? `${formatInt(latestEbikes)} of the ${formatInt(latestBikes)} bikes available right now are e-bikes.`
        : "Not enough history yet.",
    recommendation:
      "E-bikes leave stations first on busy routes; watch their count fall in the morning peak and restock e-bikes where it drops fastest.",
    enough_data: enough,
    basis: `${formatInt(frames.length)} snapshots (bikes and e-bikes available)`,
    chart: enough
      ? {
          kind: "line",
          categories: hourly(frames.map((frame) => formatClock(frame))),
          series: [
            { name: "Bikes available", values: hourly(bikes), color: "slate" },
            { name: "E-bikes available", values: hourly(ebikes), color: "signal" },
          ],
          unit: "bikes",
        }
      : null,
  };
}

/** The Insights page in snapshot mode. */
export async function buildSnapshotInsights(): Promise<InsightsResponse | null> {
  const [history, daily, live] = await Promise.all([getHistory(), getDailyKpis(), getLive()]);
  if (!history && !daily && !live) return null;
  return {
    as_of: live?.kpis.as_of ?? history?.generated_at ?? new Date().toISOString(),
    findings: [
      workRightNow(live?.kpis ?? null),
      emptyThroughTheDay(history),
      availabilityByDay(daily),
      ebikesThroughTheDay(history),
    ],
  };
}
