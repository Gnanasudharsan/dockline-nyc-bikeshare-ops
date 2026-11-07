# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
phases are tagged `phase-N` until the `v1.0.0` release.

## [Unreleased]

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
