# 0002. PostgreSQL + TimescaleDB as the warehouse

- Status: Accepted
- Date: 2026-11-06

## Context
About 2,500 stations reporting every 60 seconds is roughly 3.6 million rows per day.
We need fast time-bucketed queries for live dashboards, cheap long-term history, SQL
compatibility for dbt, Cube, Grafana and Power BI, and it must run free on a single
4-core ARM VM.

## Decision
Use PostgreSQL 16 with the TimescaleDB extension (`timescale/timescaledb` image,
multi-arch). Raw snapshots go into hypertables, compressed after 7 days and dropped
after 30 days. Continuous aggregates at 5-minute and hourly grain are kept forever.

## Consequences
- One database engine for raw, modeled, and serving data; every downstream tool speaks Postgres.
- Compression keeps disk use small enough for the free VM.
- Raw minute-level history older than 30 days is gone by design; analysis beyond that uses aggregates.
- Rejected: ClickHouse (faster scans, but weaker dbt/Power BI/Cube story and more ops
  for one person), DuckDB/MotherDuck (not a concurrent always-on server), managed cloud
  warehouses (not free at this ingest rate).
