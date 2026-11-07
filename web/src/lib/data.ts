// Server-side page data that depends on the deployment mode (src/lib/mode.ts).

import { getApiInsights, getApiLiveKpis } from "./api";
import { IS_SNAPSHOT } from "./mode";
import { getLive } from "./snapshot";
import { buildSnapshotInsights } from "./snapshotInsights";
import type { InsightsResponse, LiveKpis } from "./types";

/** Live KPIs for the first paint: from the API, or computed from the feed in snapshot mode. */
export async function getLiveKpis(): Promise<LiveKpis | null> {
  if (IS_SNAPSHOT) return (await getLive())?.kpis ?? null;
  return getApiLiveKpis();
}

/** Insights: from the API, or built from the snapshot history in snapshot mode. */
export async function getInsights(): Promise<InsightsResponse | null> {
  return IS_SNAPSHOT ? buildSnapshotInsights() : getApiInsights();
}
