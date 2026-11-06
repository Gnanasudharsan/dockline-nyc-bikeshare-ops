# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
phases are tagged `phase-N` until the `v1.0.0` release.

## [Unreleased]

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
