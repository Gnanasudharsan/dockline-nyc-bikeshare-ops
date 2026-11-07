# 0012. Dagster deployment: one image, Postgres storage, serialized dbt runs

- Status: Accepted
- Date: 2026-11-07

## Context
Dagster schedules the dbt builds, runs freshness checks, and raises alerts. It needs a
webserver (UI, lineage), a daemon (schedules, sensors, run queue), persistent run
storage, and dbt in the same environment. Target hardware is a small ARM VM.

## Decision
- One image (`orchestration/Dockerfile`, `python:3.12-slim`) for both the webserver and
  the daemon. The code location loads in-process from `workspace.yaml`; dbt runs inside
  the daemon's run workers. The dbt manifest is compiled at image build time.
- Run, event, and schedule storage live in a separate `dagster` database on the
  warehouse server, created idempotently by the migrate job
  (`DOCKLINE_EXTRA_DATABASES`). No extra database container.
- `scheme: postgresql+psycopg2` in `dagster.yaml`: dagster-postgres sends
  `NOTIFY` with client-side parameters, and SQLAlchemy 2.1 defaults `postgresql://` to
  psycopg 3 (server-side binding), which Postgres rejects.
- `QueuedRunCoordinator` with a tag limit of one concurrent run for `dockline/dbt`, so
  the hourly and daily builds never overlap.
- Schedules (New York time): hourly build at :05, daily build at 00:30, raw freshness
  checks every 5 minutes. All start `RUNNING` by default.
- Alerts: a run-failure sensor and failing raw-freshness checks write to
  `ops.pipeline_events` (and a structured log line). Grafana reads that table as an
  annotation source in Phase 3. Mart freshness uses Dagster freshness policies.

## Consequences
- Two containers and no new database server; the UI is on `127.0.0.1:3070`.
- The orchestration image is large (~1.9 GB, mostly Dagster + dbt); acceptable on the VM.
- Freshness-check runs every 5 minutes add ~290 small runs a day; run history is purged
  after 30 days by Dagster's retention settings.
