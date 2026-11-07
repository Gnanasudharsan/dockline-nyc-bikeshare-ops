# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
phases are tagged `phase-N` until the `v1.0.0` release.

## [Unreleased]

## [phase-2] — 2026-11-07

### Added
- dbt project (`dbt/`): sources with freshness rules; staging views; seeds for NYC 2020
  neighborhood polygons, GBFS regions and WMO weather codes.
- Station placement by borough and neighborhood using core Postgres `polygon`
  operators, with no PostGIS (ADR 0011).
- `int_station_status_5min_filled`: an incremental station × 5-minute grid that carries
  each station's last report forward. Incremental and full-refresh runs produce
  identical rows (ADR 0010).
- Star schema:
  - dimensions: `dim_station` (SCD2 from `snap_stations`), `dim_date`, `dim_time`,
    `dim_weather`
  - facts: `fct_station_status_5min`, `fct_station_hourly`, `fct_daily_kpis`
  - snapshot: `snap_daily_kpis`, the as-of history of daily KPIs (ADR 0013)
- Operations marts: `mart_rebalancing_recommendations`, a live view, and
  `mart_chronic_stations`.
- dbt tests: 80+ data tests (dbt-utils, dbt-expectations) and dbt unit tests for the
  carry-forward and placement logic. SQLFluff linting.
- Dagster code location (`orchestration/`):
  - dbt assets grouped by layer, with the raw tables as external roots
  - schedules: hourly and daily dbt builds, and raw freshness checks every 5 minutes
  - freshness policies on marts
  - a run-failure sensor
  - alerts written to `ops.pipeline_events` (migration 0009) for Grafana annotations
    (ADR 0012)
- `dagster-webserver` (port 3070) and `dagster-daemon` Compose services. Their run
  storage is a `dagster` database created by the migrate job.
- Integration tests that run the full `dbt build` on hand-built data and assert exact
  results, plus the alert and freshness-check paths.
- CI:
  - SQLFluff and `dbt parse`
  - `dbt build` inside the orchestration image on live data
  - a check that Dagster loads with all schedules running
- `docs/metrics.md` (metrics catalog), `make dbt-build`, `make dbt-docs`,
  `make dbt-freshness`, `make dagster-dev`, `make check-pipeline`.

### Changed
- The ingestion image installs only the ingestion and warehouse packages.

## [phase-1] — 2026-11-07

### Added
- Ingestion service (`ingestion/`): async poller for GBFS `station_status` (every feed
  ttl), `station_information` (hourly) and Open-Meteo hourly weather. GBFS feeds are
  resolved through auto-discovery, preferring v2.3. Per-record Pydantic v2 validation
  with counted rejection reasons, idempotent `unnest` batch writes, tenacity retries
  with jittered backoff, graceful SIGTERM shutdown, heartbeat healthcheck, JSON logs.
- Warehouse migrations (`warehouse/`): `raw.station_status` hypertable (unique on
  `station_id, last_reported`, compressed after 7 days, dropped after 30),
  `raw.station_information`, `raw.weather_hourly`, `ops.ingestion_runs` audit log, and
  5-minute and hourly continuous aggregates kept forever.
- In-house migration runner with checksums, advisory locking and no-transaction
  support, run as the one-shot `migrate` Compose service.
- Unit tests on recorded feed fixtures and end-to-end integration tests against a
  throwaway TimescaleDB container (testcontainers).
- CI: integration tests, plus a live smoke test that builds the stack and checks that
  real GBFS rows land.
- `make migrate`, `make psql`, `make test-unit`, `make check-ingestion`.
- ADR 0006 (raw status storage model) and ADR 0007 (migration runner).

### Fixed
- station_status polls are scheduled from the feed's `last_updated + ttl` instead of
  a fixed 60 s timer, which could phase-lock just before each feed refresh and miss
  a version (found during the acceptance run; ADR 0008).
- station_status uses ETag conditional requests, so checks for a new version return
  an empty 304 instead of re-downloading an unchanged payload. Runs record
  `not_modified` (migration 0008, ADR 0009).

## [phase-0] — 2026-11-06

### Added
- Monorepo layout for ingestion, warehouse, dbt, orchestration, semantic layer,
  Grafana, Power BI, API, web, infra and docs.
- Docker Compose skeleton with a TimescaleDB 2.31 (PostgreSQL 16) service, healthcheck,
  restart policy and resource limits; Postgres bound to localhost by default.
- `.env.example`, `.gitignore`, `.editorconfig`, pre-commit hooks (ruff, mypy,
  gitleaks, YAML/JSON checks).
- Makefile with `setup`, `up`, `down`, `test`, `lint`, `logs`.
- Repository hygiene tests that enforce healthchecks, restart policies, resource
  limits, and that every Compose variable is documented in `.env.example`.
- GitHub Actions CI: lint, type-check, test, secret scan, Compose validation.
- `CLAUDE.md` project spec, ADRs 0001–0005, MIT license.
