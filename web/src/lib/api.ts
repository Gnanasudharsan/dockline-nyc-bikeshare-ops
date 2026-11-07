import type { InsightsResponse, LiveKpis, MetricsCatalog } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8070").replace(
  /\/$/,
  "",
);
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3010").replace(
  /\/$/,
  "",
);
export const GRAFANA_URL = (process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3060").replace(
  /\/$/,
  "",
);
export const GRAFANA_PUBLIC_DASHBOARD = process.env.NEXT_PUBLIC_GRAFANA_PUBLIC_DASHBOARD ?? "";
export const REPO_URL = "https://github.com/Gnanasudharsan/dockline-nyc-bikeshare-ops";

/**
 * Fetch JSON from the API on the server, with a revalidation window.
 * Returns null instead of throwing, so pages render a graceful state when the API is down.
 */
async function getJson<T>(path: string, revalidateSeconds: number): Promise<T | null> {
  try {
    const response = await fetch(`${API_URL}${path}`, {
      next: { revalidate: revalidateSeconds },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export const getApiLiveKpis = () => getJson<LiveKpis>("/v1/kpis/live", 10);
export const getApiInsights = () => getJson<InsightsResponse>("/v1/insights", 900);
export const getMetrics = () => getJson<MetricsCatalog>("/v1/metrics", 3600);
