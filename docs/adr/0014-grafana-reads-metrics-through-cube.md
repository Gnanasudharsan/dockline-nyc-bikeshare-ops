# 0014. Grafana reads metrics through Cube's SQL API

- Status: Accepted
- Date: 2026-11-07

## Context
Cube is the only place metrics may be defined (ADR 0003). Grafana has no native Cube
datasource, and the usual setup — Grafana's Postgres datasource pointed straight at the
warehouse — would mean writing `sum(empty_minutes)`, the fill-ratio formula, and so on
again in dashboard SQL, where they would drift from Cube, Power BI, and the API.

## Decision
- Cube exposes its **SQL API** (Postgres wire protocol, port 15432). Grafana's built-in
  Postgres datasource (`uid: cube`) connects to it, and every panel selects
  `MEASURE(<metric>)` from a cube. Grafana's `$__timeFilter` macro produces plain
  `BETWEEN` filters, which Cube pushes down; grouping uses `date_trunc('minute', ...)`
  (5-minute facts are already bucket-aligned).
- A second datasource (`uid: warehouse`, read-only role) is used only for things that
  are not business metrics: pipeline-event annotations, the ingestion-failure alert,
  and computing the time-travel bucket.
- A test fails if any panel target uses a datasource other than Cube, and
  `grafana/check_dashboards.py` runs every panel query through Grafana in CI.

## Consequences
- One definition per metric, shared by Grafana, the API (Phase 5), and the website.
- Cube caches and pre-aggregates, so 10-second refresh on several dashboards stays cheap.
- Grafana's visual query builder does not understand cubes; dashboards are written as
  SQL in `grafana/build_dashboards.py`, which suits dashboards-as-code anyway.
