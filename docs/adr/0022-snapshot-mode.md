# 0022. Snapshot mode: a public deployment without a server

- Status: Accepted
- Date: 2026-11-07

## Context

The full stack (ADR 0020, 0021) needs an always-on server, and Oracle Cloud's free ARM
capacity was not available. The project still needs a public, working site at $0 that
shows live data honestly and keeps the "one definition per metric" rule.

## Decision

The website gets a second deployment mode, `NEXT_PUBLIC_DEPLOY_MODE=snapshot` (the
default stays `full`). Switching back is an environment change, not a code change.

- **Live layer:** the Next.js route `/api/live` on Vercel fetches GBFS (same
  discovery rules as ingestion, ADR 0005) and computes the certified point-in-time
  metrics in `web/src/lib/metrics.ts`. The CDN caches it for 30 s with 30 s of
  stale-while-revalidate, so numbers are at most about a minute older than the feed.
  If the feed fails, it serves the last snapshot and says so (`source: "snapshot"`).
- **History layer:** `.github/workflows/snapshot.yml` runs every 10 minutes and uses
  `dockline_ingestion.kpis` and `.snapshot` (the ingestion validators and the same
  rules) to write `latest.json`, `history-24h.json` (10-minute frames) and
  `daily-kpis.json` (30 days). They live on an orphan `data` branch kept at one
  commit that each run replaces by force-push, so `main` stays clean and the
  repository does not grow. The site reads them through `/api/snapshot/<name>` (2-minute
  cache). Overlapping runs cancel; failed scheduled runs email the owner.
- **One definition, two languages:** the full stack defines metrics in dbt and Cube.
  Snapshot mode has no warehouse, so the point-in-time rules exist in Python and
  TypeScript. Both run on one recorded GBFS poll with edge cases
  (`tests/fixtures/gbfs_parity`) and must produce the identical expected output, in
  pytest and in the website's CI job. A test also keeps both sets of thresholds equal
  to the dbt vars. The Python version was checked against Cube's live numbers.
- **Pages:** Home uses `/api/live` with a freshness line ticking from the feed's own
  timestamp. Live replaces the Grafana embed with the 10-minute replay and ECharts
  trend panels. Insights are rebuilt from the history. Ask shows a note, because Ask
  the Data needs Cube and an LLM. How it works explains the two modes.

## Consequences

- No warehouse in this mode: no per-minute history, no Grafana alerts, no Power BI, no
  Ask the Data. Time-weighted metrics are sampled every 10 minutes, and GitHub's
  scheduler can delay or skip runs, so daily figures are estimates from the samples
  taken (rates stay correct; station-minutes undercount when runs are missed).
- GitHub disables scheduled workflows in a public repository after 60 days without
  activity on the default branch; a commit to `main` re-enables them.
- Vercel ignores the `data` branch (`web/vercel.json`), so snapshots never trigger
  deployments.
- Cost: $0 (Vercel Hobby, GitHub Actions minutes for a public repository).

## Update (2026-11-11): two fixes after four days in production
- **Frozen live numbers.** On Vercel, the ISR routes and Next's fetch cache never
  refreshed: `/api/live` served the copy built at deploy time for three days, while
  the same build refreshed correctly under `next start`. The API routes are now
  dynamic (`force-dynamic`, upstream fetches `no-store`) and cached only by Vercel's
  CDN (`Vercel-CDN-Cache-Control: max-age=30, stale-while-revalidate=30`; 120 s for
  history). Snapshot-mode pages hold no server data: Home and Live load it in the
  browser from those routes, and Insights renders per request.
- **Sparse history.** GitHub ran the `*/10` schedule only every 4-8 hours. The
  Snapshot workflow now loops inside one run, taking a snapshot at every 10-minute
  mark for about 5.5 hours, then starts its successor with `workflow_dispatch`. An
  hourly schedule restarts the chain if it breaks. This keeps one runner busy most of
  the time, which is free for public repositories; if GitHub objects, the
  alternative is an external free cron calling `workflow_dispatch` every 10 minutes.
