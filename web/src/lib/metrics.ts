// Certified point-in-time KPIs from one GBFS poll, for snapshot mode's /api/live.
//
// This is the TypeScript twin of ingestion/src/dockline_ingestion/kpis.py, which applies
// the definitions in docs/metrics.md (dbt fct_station_status_5min and the fleet_status
// cube). Both are checked against the same recorded fixture and expected output
// (tests/fixtures/gbfs_parity), in pytest and in web/test/metrics-parity.test.mjs, and a
// test keeps the constants below equal to the dbt vars. Keep this file free of runtime
// imports so Node can run it directly in that test.

import type { ImbalanceState, LiveKpis, Station } from "./types";

export const STALE_REPORT_MINUTES = 30;
export const TARGET_FILL_RATIO = 0.5;
export const STARVING_FILL_RATIO = 0.2;
export const FLOODING_FILL_RATIO = 0.8;

// Inactive stations report last_reported = 86400; anything before Citi Bike's launch
// is a placeholder. Reports more than 10 minutes in the future are rejected too.
const EARLIEST_PLAUSIBLE_REPORT = Date.UTC(2013, 0, 1) / 1000;
const MAX_FUTURE_SKEW_SECONDS = 600;
const MAX_COUNT = 32_767;

export interface LiveSnapshot {
  kpis: LiveKpis;
  stations: Station[];
}

interface StatusRecord {
  station_id: string;
  last_reported: number;
  bikes: number;
  ebikes: number;
  docks: number;
  is_installed: boolean;
  is_renting: boolean;
  is_returning: boolean;
}

interface InfoRecord {
  station_id: string;
  name: string;
  lat: number;
  lon: number;
}

type Json = Record<string, unknown>;

/** Whole epoch seconds as YYYY-MM-DDTHH:MM:SSZ (same format as the Python side). */
export function isoUtc(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
}

/** PostgreSQL round(numeric): halves go away from zero. */
export function roundHalfAwayFromZero(value: number): number {
  return Math.sign(value) * Math.floor(Math.abs(value) + 0.5);
}

function isCount(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= MAX_COUNT;
}

function asBool(value: unknown): boolean | null {
  if (value === true || value === 1) return true;
  if (value === false || value === 0) return false;
  return null;
}

function optionalString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === "string";
}

function stationsOf(payload: unknown): Json[] {
  const data = (payload as { data?: { stations?: unknown } } | null)?.data;
  if (!data || !Array.isArray(data.stations)) throw new Error("GBFS payload has no stations");
  return data.stations as Json[];
}

/** Validate station_status records the way the ingestion service does (models.py). */
function parseStatus(payload: unknown, nowEpoch: number): StatusRecord[] {
  const records: StatusRecord[] = [];
  const seen = new Set<string>();
  for (const raw of stationsOf(payload)) {
    const docks = raw.num_docks_available;
    const bikes = raw.num_bikes_available;
    const ebikes = raw.num_ebikes_available ?? 0;
    const flags = [raw.is_installed, raw.is_renting, raw.is_returning].map(asBool);
    const optionalCounts = [raw.num_bikes_disabled ?? 0, raw.num_docks_disabled ?? 0];
    if (
      typeof raw.station_id !== "string" ||
      raw.station_id.length === 0 ||
      typeof raw.last_reported !== "number" ||
      !Number.isFinite(raw.last_reported) ||
      !isCount(bikes) ||
      !isCount(docks) ||
      !isCount(ebikes) ||
      !optionalCounts.every(isCount) ||
      flags.some((flag) => flag === null)
    ) {
      continue; // invalid
    }
    if (raw.last_reported < EARLIEST_PLAUSIBLE_REPORT) continue; // never reported
    if (raw.last_reported > nowEpoch + MAX_FUTURE_SKEW_SECONDS) continue; // future timestamp
    const key = `${raw.station_id}\u0000${raw.last_reported}`;
    if (seen.has(key)) continue; // duplicate
    seen.add(key);
    records.push({
      station_id: raw.station_id,
      last_reported: Math.trunc(raw.last_reported),
      bikes,
      ebikes,
      docks,
      is_installed: flags[0] as boolean,
      is_renting: flags[1] as boolean,
      is_returning: flags[2] as boolean,
    });
  }
  return records;
}

/** Validate station_information records the way the ingestion service does. */
function parseInformation(payload: unknown): InfoRecord[] {
  const records: InfoRecord[] = [];
  const seen = new Set<string>();
  for (const raw of stationsOf(payload)) {
    const { station_id: id, name, lat, lon, capacity } = raw;
    if (
      typeof id !== "string" ||
      id.length === 0 ||
      typeof name !== "string" ||
      name.length === 0 ||
      typeof lat !== "number" ||
      lat < -90 ||
      lat > 90 ||
      typeof lon !== "number" ||
      lon < -180 ||
      lon > 180 ||
      !(capacity === undefined || capacity === null || isCount(capacity)) ||
      !optionalString(raw.short_name) ||
      !optionalString(raw.region_id) ||
      !(
        raw.is_charging === undefined ||
        raw.is_charging === null ||
        asBool(raw.is_charging) !== null
      )
    ) {
      continue;
    }
    if (seen.has(id)) continue;
    seen.add(id);
    records.push({ station_id: id, name, lat, lon });
  }
  return records;
}

interface Classified {
  station: Station;
  ebikes: number | null;
  inService: boolean;
  available: boolean;
  bikesToMove: number;
}

function classify(
  info: InfoRecord,
  status: StatusRecord | undefined,
  nowEpoch: number,
): Classified {
  const inService =
    status !== undefined &&
    !(nowEpoch - status.last_reported > STALE_REPORT_MINUTES * 60) &&
    status.is_installed &&
    (status.is_renting || status.is_returning);
  let state: ImbalanceState = "offline";
  let bikesToMove = 0;
  let available = false;
  if (inService && status) {
    const { bikes, docks } = status;
    const slots = bikes + docks;
    const fill = slots ? bikes / slots : null;
    if (bikes === 0 || (fill !== null && fill <= STARVING_FILL_RATIO)) state = "starving";
    else if (docks === 0 || (fill !== null && fill >= FLOODING_FILL_RATIO)) state = "flooding";
    else state = "balanced";
    const need = roundHalfAwayFromZero(TARGET_FILL_RATIO * slots) - bikes;
    if (state === "starving" || state === "flooding") bikesToMove = Math.abs(need);
    available = status.is_renting && status.is_returning && bikes >= 1 && docks >= 1;
  }
  return {
    station: {
      station_id: info.station_id,
      station_name: info.name,
      latitude: info.lat,
      longitude: info.lon,
      imbalance_state: state,
      station_bikes_available: status ? status.bikes : null,
      station_docks_available: status ? status.docks : null,
    },
    ebikes: status ? status.ebikes : null,
    inService,
    available,
    bikesToMove,
  };
}

/**
 * KPIs and stations for one poll. `nowEpoch` is passed in so results are reproducible.
 * Throws if either payload is not a GBFS station feed.
 */
export function computeLive(
  statusPayload: unknown,
  informationPayload: unknown,
  nowEpoch: number,
): LiveSnapshot {
  const latest = new Map<string, StatusRecord>();
  for (const record of parseStatus(statusPayload, nowEpoch)) {
    const current = latest.get(record.station_id);
    if (!current || record.last_reported > current.last_reported) {
      latest.set(record.station_id, record);
    }
  }
  const listed = parseInformation(informationPayload).sort((a, b) =>
    a.station_id < b.station_id ? -1 : a.station_id > b.station_id ? 1 : 0,
  );
  const rows = listed.map((info) => classify(info, latest.get(info.station_id), nowEpoch));
  const inService = rows.filter((row) => row.inService);

  const bikes = inService.reduce((sum, row) => sum + (row.station.station_bikes_available ?? 0), 0);
  const docks = inService.reduce((sum, row) => sum + (row.station.station_docks_available ?? 0), 0);
  const reported = listed.flatMap((info) => {
    const status = latest.get(info.station_id);
    return status ? [status.last_reported] : [];
  });
  const feedUpdated = (statusPayload as { last_updated?: unknown }).last_updated;
  const count = (state: ImbalanceState) =>
    rows.filter((row) => row.station.imbalance_state === state).length;

  const kpis: LiveKpis = {
    as_of: isoUtc(nowEpoch),
    feed_updated_at: typeof feedUpdated === "number" ? isoUtc(Math.trunc(feedUpdated)) : null,
    bikes_available: bikes,
    ebikes_available: inService.reduce((sum, row) => sum + (row.ebikes ?? 0), 0),
    docks_available: docks,
    fill_ratio: bikes + docks ? bikes / (bikes + docks) : null,
    stations: rows.length,
    stations_in_service: inService.length,
    empty_stations: inService.filter((row) => row.station.station_bikes_available === 0).length,
    full_stations: inService.filter((row) => row.station.station_docks_available === 0).length,
    available_stations: rows.filter((row) => row.available).length,
    starving_stations: count("starving"),
    balanced_stations: count("balanced"),
    flooding_stations: count("flooding"),
    offline_stations: count("offline"),
    rebalance_need_bikes: rows.reduce((sum, row) => sum + row.bikesToMove, 0),
    data_freshness_seconds: reported.length ? nowEpoch - Math.max(...reported) : null,
  };
  return { kpis, stations: rows.map((row) => row.station) };
}
