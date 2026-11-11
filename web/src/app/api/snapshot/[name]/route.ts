import { SNAPSHOT_FILES, type SnapshotFile } from "@/lib/mode";
import { getSnapshotFile } from "@/lib/snapshot";

// Same-origin access to the snapshot workflow's files (history for the replay and
// charts). Only the files in SNAPSHOT_FILES can be read. Dynamic, and cached on
// Vercel's CDN for 2 minutes (GitHub raw adds up to 5), for the same reason as
// /api/live.
export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ name: string }> }) {
  const { name } = await context.params;
  if (!Object.hasOwn(SNAPSHOT_FILES, name)) {
    return Response.json({ error: "Unknown file." }, { status: 404 });
  }
  const { cdnSeconds } = SNAPSHOT_FILES[name as SnapshotFile];
  const data = await getSnapshotFile<unknown>(name as SnapshotFile);
  if (!data) {
    return Response.json(
      { error: "The snapshot history is unavailable right now. Try again in a few minutes." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
  return Response.json(data, {
    headers: {
      "Cache-Control": "public, max-age=60",
      "Vercel-CDN-Cache-Control": `max-age=${cdnSeconds}, stale-while-revalidate=${cdnSeconds}`,
    },
  });
}
