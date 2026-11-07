// Shapes returned by the Dockline API (api/src/dockline_api).

export type ImbalanceState = "starving" | "balanced" | "flooding" | "offline";

export interface LiveKpis {
  as_of: string;
  bikes_available: number;
  ebikes_available: number;
  docks_available: number;
  fill_ratio: number;
  stations: number;
  stations_in_service: number;
  empty_stations: number;
  full_stations: number;
  starving_stations: number;
  balanced_stations: number;
  flooding_stations: number;
  offline_stations: number;
  rebalance_need_bikes: number;
  data_freshness_seconds: number;
}

export interface Station {
  station_id: string;
  station_name: string;
  borough: string;
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
