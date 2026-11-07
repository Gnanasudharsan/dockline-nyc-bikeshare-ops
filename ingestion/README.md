# ingestion

Always-on Python 3.12 service that polls the public Citi Bike GBFS feed and Open-Meteo
and writes validated rows into TimescaleDB.

| Job | Schedule | Writes to |
| --- | --- | --- |
| `station_status` | when the current version expires (`last_updated + ttl + 5 s`); conditional `If-None-Match` checks every 10 s while unchanged (ADRs 0008, 0009) | `raw.station_status` |
| `station_information` | hourly, and at startup (also re-resolves GBFS discovery) | `raw.station_information` |
| `weather_hourly` | hourly (last 2 days + today's forecast) | `raw.weather_hourly` |

Every poll writes one row to `ops.ingestion_runs` with counts of records fetched,
inserted, duplicate (no new report since the last poll), and rejected (by reason).

## How it works

- **Discovery** (`sources.py`): reads `gbfs.json`, follows `gbfs_versions` to the
  preferred version (2.3), and resolves feed URLs. See ADR 0005.
- **Validation** (`models.py`): Pydantic v2 validates each station on its own, so one bad
  record never drops a poll. Placeholder timestamps (`86400`) are rejected as
  `never_reported`.
- **Writes** (`repository.py`): one `INSERT ... SELECT FROM unnest(...)` per poll with
  `ON CONFLICT` on `(station_id, last_reported)`, so writes are idempotent. See ADR 0006.
- **Resilience**: HTTP retries with exponential backoff and jitter for timeouts, 429s,
  and 5xx responses (tenacity). A failed job is recorded and retried on its next tick
  without affecting the other jobs.
- **Shutdown**: SIGTERM/SIGINT lets in-flight polls finish (30 s grace), then exits.
- **Health**: each successful status poll touches a heartbeat file, and the container
  healthcheck fails if it is older than 3 minutes.
- **Logs**: JSON lines on stdout (structlog).

## Run

```bash
make up                 # builds the image, runs migrations, starts polling
docker compose logs -f ingestion
make check-ingestion    # acceptance queries
```

## Test

```bash
make test-unit          # parsing, retries, scheduling (no Docker)
make test               # plus end-to-end tests against a throwaway TimescaleDB container
```

Fixtures in `tests/fixtures/` are trimmed recordings of the real feeds (captured
2026-11-07).
