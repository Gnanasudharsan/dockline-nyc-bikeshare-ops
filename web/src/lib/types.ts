// Shapes returned by the Dockline API (api/src/dockline_api).

export type ImbalanceState = "starving" | "balanced" | "flooding" | "offline";

export interface LiveKpis {
  as_of: string;
  /** The feed's own last_updated time (snapshot mode only). */
  feed_updated_at?: string | null;
  bikes_available: number;
  ebikes_available: number;
  docks_available: number;
  fill_ratio: number | null;
  stations: number;
  stations_in_service: number;
  empty_stations: number;
  full_stations: number;
  /** In service, renting and returning, with at least one bike and one dock (snapshot mode). */
  available_stations?: number;
  starving_stations: number;
  balanced_stations: number;
  flooding_stations: number;
  offline_stations: number;
  rebalance_need_bikes: number;
  data_freshness_seconds: number | null;
}

export interface Station {
  station_id: string;
  station_name: string;
  borough?: string;
  latitude: number;
  longitude: number;
  imbalance_state: ImbalanceState;
  station_bikes_available: number | null;
  station_docks_available: number | null;
}

export interface StationsResponse {
  as_of: string;
  count: number;
  stations: Station[];
}

export interface ReplayResponse {
  hours: string[];
  legend: Record<ImbalanceState, string>;
  stations: Record<string, string>;
}

export interface MetricDefinition {
  name: string;
  definition: string;
  unit: string;
}

export interface MetricsCatalog {
  topics: {
    name: string;
    description: string;
    measures: MetricDefinition[];
    dimensions: { name: string; definition: string }[];
    time_ranges: string[];
  }[];
  example_questions: string[];
}

export interface AskResponse {
  question: string;
  status: "answered" | "refused" | "error";
  answer: string;
  metrics: MetricDefinition[];
  query: Record<string, unknown> | null;
  rows: Record<string, string | number | boolean | null>[];
  data_freshness_seconds: number | null;
  suggestion: string | null;
  answer_source: "model" | "template" | "none";
  elapsed_ms: number;
}

export type TokenColor = "signal" | "starving" | "flooding" | "balanced" | "offline" | "slate";

export interface Finding {
  id: string;
  title: string;
  finding: string;
  recommendation: string;
  enough_data: boolean;
  basis: string;
  chart: {
    kind: "bar" | "column" | "line";
    categories: string[];
    series: { name: string; values: (number | null)[]; color: TokenColor }[];
    unit: "percent" | "count" | "bikes";
  } | null;
}

export interface InsightsResponse {
  as_of: string;
  findings: Finding[];
}

// Snapshot mode (ADR 0022): /api/live and the data branch files.

export interface LiveResponse {
  kpis: LiveKpis;
  stations: Station[];
  /** "feed": computed from the live GBFS feed now; "snapshot": the workflow's last run. */
  source: "feed" | "snapshot";
}

export interface LatestSnapshot {
  generated_at: string;
  kpis: LiveKpis;
  stations: Station[];
  weather: {
    observed_hour: string;
    temperature_c: number | null;
    precipitation_mm: number | null;
    weather_code: number | null;
    condition: string;
  } | null;
}

export type SeriesKey =
  | "bikes_available"
  | "ebikes_available"
  | "docks_available"
  | "fill_ratio"
  | "empty_stations"
  | "full_stations"
  | "starving_stations"
  | "balanced_stations"
  | "flooding_stations"
  | "offline_stations"
  | "rebalance_need_bikes";

export interface History24h {
  generated_at: string;
  interval_minutes: number;
  frames: string[];
  legend: Record<string, string>;
  stations: Record<string, string>;
  series: Record<SeriesKey, (number | null)[]>;
}

export interface DailyKpisDay {
  date: string;
  samples: number;
  availability_rate: number | null;
  empty_station_minutes: number;
  full_station_minutes: number;
  avg_bikes_available: number;
  avg_docks_available: number;
  max_empty_stations: number;
  max_full_stations: number;
}

export interface DailyKpis {
  generated_at: string;
  interval_minutes: number;
  days: DailyKpisDay[];
}
