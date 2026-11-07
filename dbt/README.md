# dbt

The Dockline dbt project (dbt Core + dbt-postgres) turns raw GBFS and weather data
into a star schema. It runs hourly and daily under Dagster (`orchestration/`).

```
sources (raw.*, agg.*, ops.*)
  └─ staging/        views: renamed, typed, one model per source table
      └─ intermediate/  station placement + the carried-forward 5-minute grid
          ├─ snapshots/   snap_stations (SCD2), snap_daily_kpis (as-of)
          └─ marts/
              ├─ core/   dim_station, dim_date, dim_time, dim_weather,
              │          fct_station_status_5min, fct_station_hourly, fct_daily_kpis
              └─ ops/    mart_rebalancing_recommendations (live view),
                         mart_chronic_stations
```

| Schema | Contents |
| --- | --- |
| `staging` | `stg_gbfs__station_information`, `stg_gbfs__station_status_5min`, `stg_open_meteo__weather_hourly`, `stg_ops__ingestion_runs` |
| `intermediate` | `int_station_locations`, `int_station_status_5min_filled` (incremental) |
| `snapshots` | `snap_stations`, `snap_daily_kpis` |
| `marts` | dimensions, facts, and operational marts above |
| `reference` | seeds: NYC neighborhoods (polygons), GBFS regions, WMO weather codes |

Key design notes:
- **Carry-forward grid** ([ADR 0010](../docs/adr/0010-station-state-grid.md)): quiet
  stations add no raw rows, so the 5-minute grid fills every bucket with the last known
  state. Minute metrics are additive columns (`empty_minutes`, `available_minutes`, ...).
- **Boroughs without PostGIS** ([ADR 0011](../docs/adr/0011-borough-mapping-without-postgis.md)):
  core Postgres `polygon @> point`.
- **History** ([ADR 0013](../docs/adr/0013-history-snapshots.md)): SCD2 stations and an
  as-of snapshot of daily KPIs.
- Tunable thresholds (stale minutes, target fill, peak hours, chronic threshold,
  retention) are `vars` in `dbt_project.yml`. `as_of` pins "now" for reproducible runs.

Tests: generic tests, dbt-utils and dbt-expectations tests, plus dbt **unit tests** for
the carry-forward logic and station placement. `orchestration/tests` also runs the full
`dbt build` against a throwaway TimescaleDB with hand-built data and checks exact
numbers.

## Run it

From the repository root (reads `.env`, connects to the published port 5433):

```bash
make dbt-deps
make dbt-build
make dbt-docs        # lineage and column docs on http://localhost:8080
make dbt-freshness
```

SQL style is enforced with SQLFluff (`dbt/.sqlfluff`, run by pre-commit and CI).

To regenerate the neighborhood seed, see `scripts/build_neighborhood_seed.py`.
