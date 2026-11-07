import { getLive, LIVE_REVALIDATE_SECONDS } from "@/lib/snapshot";

// Snapshot mode's live endpoint: certified point-in-time KPIs and every station's
// state, computed from the public GBFS feed (src/lib/metrics.ts). Cached briefly on
// the CDN so the feed is read at most about twice a minute.
export const revalidate = 30;

export async function GET() {
  const live = await getLive();
  if (!live) {
    return Response.json(
      {
        error:
          "The station feed and the last snapshot are both unavailable. Try again in a minute.",
      },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
  return Response.json(live, {
    headers: {
      "Cache-Control": `public, max-age=0, s-maxage=${LIVE_REVALIDATE_SECONDS}, stale-while-revalidate=${LIVE_REVALIDATE_SECONDS}`,
    },
  });
}
