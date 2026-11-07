// Server-side data for snapshot mode: live KPIs straight from the GBFS feed, and the
// history files from the data branch. Every function returns null instead of throwing,
// so pages render their unavailable states.

import { computeLive, type LiveSnapshot } from "./metrics";
import { SNAPSHOT_DATA_URL, SNAPSHOT_FILES, type SnapshotFile } from "./mode";
import type { DailyKpis, History24h, LatestSnapshot, LiveResponse } from "./types";

// Same discovery rules as the ingestion service (ADR 0005): start from gbfs.json and
// prefer GBFS 2.3 when gbfs_versions lists it.
const DISCOVERY_URL = "https://gbfs.citibikenyc.com/gbfs/gbfs.json";
const PREFERRED_VERSION = "2.3";
const PREFERRED_LANGUAGE = "en";
/** Live feed cache: with the route's own 30 s window, numbers are at most ~60 s old. */
export const LIVE_REVALIDATE_SECONDS = 30;

interface Discovery {
  version?: string;
  data: Record<string, { feeds: { name: string; url: string }[] }>;
}

async function getJson<T>(url: string, revalidate: number): Promise<T> {
  const response = await fetch(url, {
    next: { revalidate },
    signal: AbortSignal.timeout(10_000),
    headers: {
      "User-Agent": "dockline-web (+https://github.com/Gnanasudharsan/dockline-nyc-bikeshare-ops)",
    },
  });
  if (!response.ok) throw new Error(`${url} answered ${response.status}`);
  return (await response.json()) as T;
}

function feedsByName(discovery: Discovery): Record<string, string> {
  const language = discovery.data[PREFERRED_LANGUAGE] ?? Object.values(discovery.data)[0];
  if (!language) throw new Error("GBFS discovery lists no languages");
  return Object.fromEntries(language.feeds.map((feed) => [feed.name, feed.url]));
}

async function resolveFeeds(): Promise<{ status: string; information: string }> {
  let discovery = await getJson<Discovery>(DISCOVERY_URL, 3600);
  let feeds = feedsByName(discovery);
  if (feeds.gbfs_versions && discovery.version !== PREFERRED_VERSION) {
    const versions = await getJson<{ data: { versions: { version: string; url: string }[] } }>(
      feeds.gbfs_versions,
      3600,
    );
    const preferred = versions.data.versions.find(
      (candidate) => candidate.version.replace(/^v/, "") === PREFERRED_VERSION,
    );
    if (preferred) {
      discovery = await getJson<Discovery>(preferred.url, 3600);
      feeds = feedsByName(discovery);
    }
  }
  if (!feeds.station_status || !feeds.station_information) {
    throw new Error("GBFS discovery is missing station feeds");
  }
  return { status: feeds.station_status, information: feeds.station_information };
}

/** A snapshot file from the data branch, or null if it cannot be read. */
export async function getSnapshotFile<T>(name: SnapshotFile): Promise<T | null> {
  const { file, revalidate } = SNAPSHOT_FILES[name];
  try {
    return await getJson<T>(`${SNAPSHOT_DATA_URL}/${file}`, revalidate);
  } catch {
    return null;
  }
}

export const getHistory = () => getSnapshotFile<History24h>("history-24h");
export const getDailyKpis = () => getSnapshotFile<DailyKpis>("daily-kpis");
export const getLatest = () => getSnapshotFile<LatestSnapshot>("latest");

/**
 * Live KPIs and stations computed from the public feed now. If the feed cannot be
 * read, falls back to the workflow's latest snapshot (marked `source: "snapshot"`).
 */
export async function getLive(): Promise<LiveResponse | null> {
  try {
    const feeds = await resolveFeeds();
    const [status, information] = await Promise.all([
      getJson<unknown>(feeds.status, LIVE_REVALIDATE_SECONDS),
      getJson<unknown>(feeds.information, 3600),
    ]);
    const live: LiveSnapshot = computeLive(status, information, Math.floor(Date.now() / 1000));
    return { ...live, source: "feed" };
  } catch {
    const latest = await getLatest();
    return latest ? { kpis: latest.kpis, stations: latest.stations, source: "snapshot" } : null;
  }
}
