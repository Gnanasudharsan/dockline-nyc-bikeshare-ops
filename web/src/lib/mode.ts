// Deployment mode (ADR 0022). "full": the self-hosted stack (warehouse, Cube, Grafana,
// API). "snapshot": Vercel only; live numbers come from the public feed through
// /api/live, and history from JSON files that a GitHub Actions workflow publishes.
// Switching back to the full stack is only a change of NEXT_PUBLIC_DEPLOY_MODE.

export type DeployMode = "full" | "snapshot";

export const DEPLOY_MODE: DeployMode =
  process.env.NEXT_PUBLIC_DEPLOY_MODE === "snapshot" ? "snapshot" : "full";
export const IS_SNAPSHOT = DEPLOY_MODE === "snapshot";

/** Where the snapshot workflow publishes its files (the repository's `data` branch). */
export const SNAPSHOT_DATA_URL = (
  process.env.SNAPSHOT_DATA_URL ??
  "https://raw.githubusercontent.com/Gnanasudharsan/dockline-nyc-bikeshare-ops/data"
).replace(/\/$/, "");

/** Optional link to a recorded demo of the full stack (Ask the Data, Grafana). */
export const DEMO_VIDEO_URL = process.env.NEXT_PUBLIC_DEMO_VIDEO_URL ?? "";

/** The snapshot files the site may read, and how long to cache each (seconds). */
export const SNAPSHOT_FILES = {
  latest: { file: "latest.json", revalidate: 300 },
  "history-24h": { file: "history-24h.json", revalidate: 300 },
  "daily-kpis": { file: "daily-kpis.json", revalidate: 300 },
} as const;
export type SnapshotFile = keyof typeof SNAPSHOT_FILES;
