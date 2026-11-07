# 0013. Station history (SCD2) and "as-of" daily KPIs with dbt snapshots

- Status: Accepted
- Date: 2026-11-07

## Context
Stations get renamed, move, or change capacity; analysis of last month should use the
station as it was then. Daily KPIs can be restated when late reports arrive, and a
reviewer should be able to see what a KPI said when it was first published.

## Decision
- `snap_stations` is a **timestamp-strategy** snapshot on `attributes_updated_at`.
  The ingestion service only bumps that column when a tracked attribute really changes,
  so versions open at the time the change was observed (not when dbt happened to run).
  `last_seen_at` is excluded because it moves every hour.
- `dim_station` exposes `station_key` (the snapshot's `dbt_scd_id`), `valid_from`,
  `valid_to` (`9999-12-31` for the current version), and `is_current`. The first
  version is valid from 1900 so earlier facts still resolve. Facts join on
  `station_id` and their timestamp within `[valid_from, valid_to)`.
- `snap_daily_kpis` is a **check-strategy** snapshot of `fct_daily_kpis` restricted to
  complete days. Its first version is the KPI as published; later versions record
  restatements, each stamped with `dbt_valid_from`.
- Snapshot metadata uses `now()` (timestamptz) via an override of
  `postgres__snapshot_get_time`, matching every other timestamp in the warehouse.

## Consequences
- Point-in-time correct station attributes for every fact row.
- "What did we report for 2026-11-07?" is answerable from `snap_daily_kpis` even after
  the fact table changes.
