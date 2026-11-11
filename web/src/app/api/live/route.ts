import { getLive, LIVE_CDN_SECONDS } from "@/lib/snapshot";

// Snapshot mode's live endpoint: certified point-in-time KPIs and every station's
// state, computed from the public GBFS feed (src/lib/metrics.ts).
//
// It runs on every request that reaches it; Vercel's CDN caches each response for
// LIVE_CDN_SECONDS (plus as long again while it refreshes in the background), so the
// feed is read about twice a minute however many people visit. Next's own ISR cache is
// not used: on Vercel it kept serving the build-time copy (ADR 0022).
export const dynamic = "force-dynamic";

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
      "Cache-Control": "public, max-age=0, must-revalidate",
      "Vercel-CDN-Cache-Control": `max-age=${LIVE_CDN_SECONDS}, stale-while-revalidate=${LIVE_CDN_SECONDS}`,
    },
  });
}
