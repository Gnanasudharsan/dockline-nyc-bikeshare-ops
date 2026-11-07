import { SNAPSHOT_FILES, type SnapshotFile } from "@/lib/mode";
import { getSnapshotFile } from "@/lib/snapshot";

// Same-origin access to the snapshot workflow's files (history for the replay and
// charts), cached for 5 minutes. Only the files in SNAPSHOT_FILES can be read.
export const revalidate = 300;

export function generateStaticParams() {
  return Object.keys(SNAPSHOT_FILES).map((name) => ({ name }));
}

export const dynamicParams = false;

export async function GET(_request: Request, context: { params: Promise<{ name: string }> }) {
  const { name } = await context.params;
  if (!(name in SNAPSHOT_FILES)) {
    return Response.json({ error: "Unknown file." }, { status: 404 });
  }
  const data = await getSnapshotFile<unknown>(name as SnapshotFile);
  if (!data) {
    return Response.json(
      { error: "The snapshot history is unavailable right now. Try again in a few minutes." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
  return Response.json(data, {
    headers: { "Cache-Control": "public, max-age=60, s-maxage=300, stale-while-revalidate=300" },
  });
}
