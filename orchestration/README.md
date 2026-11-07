# orchestration

Dagster OSS code location for Dockline: every dbt model, seed, and snapshot is an
asset, the raw tables written by the ingestion service are external assets at the root
of the lineage graph, and dbt tests appear as asset checks.

| Piece | What it does |
| --- | --- |
| `hourly_dbt_build` (schedule `5 * * * *`) | staging, intermediate, station snapshot, dimensions, 5-minute and hourly facts |
| `daily_dbt_build` (schedule `30 0 * * *`) | daily KPIs, as-of KPI snapshot, chronic problem stations |
| `raw_freshness_checks` (schedule `*/5 * * * *`) | fails (WARN/ERROR) when raw tables stop updating |
| Freshness policies | hourly marts warn after 75 min and fail after 2 h; daily marts fail after 26 h |
| `alert_on_run_failure` sensor | logs and records every failed run |

All schedules use New York time and start running by default. dbt builds are
serialized by a run-queue tag limit (`dockline/dbt`), so they never overlap.

**Alerts** are written to `ops.pipeline_events` (and logged as JSON). Grafana uses that
table as an annotation source (Phase 3), so failures appear as markers on dashboards.

## Run it

In Docker (part of `make up`): UI at <http://localhost:3070>.

```bash
docker compose exec dagster-daemon dagster job launch -j hourly_dbt_build \
  -w /app/orchestration/workspace.yaml
```

Locally, without Docker (UI at <http://localhost:3071>):

```bash
make dagster-dev
```

Design notes: [ADR 0012](../docs/adr/0012-dagster-deployment.md).
