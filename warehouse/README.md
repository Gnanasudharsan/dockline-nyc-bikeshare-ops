# warehouse

PostgreSQL 16 + TimescaleDB schema, managed as versioned SQL migrations.

| Schema | Object | Notes |
| --- | --- | --- |
| `raw` | `station_status` | Hypertable on `last_reported` (1-day chunks). Unique `(station_id, last_reported)`. Compressed after 7 days, dropped after 30. |
| `raw` | `station_information` | Latest attributes per station. `updated_at` changes only on real change. |
| `raw` | `weather_hourly` | Hourly NYC weather, upserted (the provider revises recent hours). |
| `agg` | `station_status_5min` | Continuous aggregate: last value per station per 5 minutes, plus min/max. Kept forever. Real-time. |
| `agg` | `station_status_hourly` | Hierarchical continuous aggregate on the 5-minute view. Kept forever. |
| `ops` | `ingestion_runs` | Audit log, one row per poll. |
| `ops` | `schema_migrations` | Applied migrations with checksums. |

## Migrations

Files live in `migrations/` as `NNNN_description.sql` and are applied in order by
`python -m dockline_warehouse` (the one-shot `migrate` Compose service). Rules:

- Never edit an applied migration; the runner refuses changed checksums. Add a new file.
- Files that create continuous aggregates start with `-- dockline:no-transaction`.

See ADR 0007 for why this is a small in-house runner.

## Checks

`checks/phase1_acceptance.sql` holds the Phase 1 acceptance queries (`make check-ingestion`).
