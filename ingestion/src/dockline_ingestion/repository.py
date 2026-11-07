"""Database writes for the ingestion service.

Each batch is written with one ``INSERT ... SELECT FROM unnest(...)`` statement: one
round trip per poll, and ``ON CONFLICT`` makes every write idempotent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from dockline_ingestion.models import StationInformation, StationStatus, WeatherHour


@dataclass
class RunStats:
    """Counts recorded in ops.ingestion_runs for one poll."""

    fetched: int = 0
    inserted: int = 0
    duplicate: int = 0
    rejected: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    source_version: str | None = None
    source_last_updated: datetime | None = None
    not_modified: bool = False


async def start_run(conn: AsyncConnection[Any], feed: str) -> int:
    """Insert a 'running' row in ops.ingestion_runs and return its run_id."""
    cursor = await conn.execute(
        "INSERT INTO ops.ingestion_runs (feed) VALUES (%s) RETURNING run_id", (feed,)
    )
    row = await cursor.fetchone()
    if row is None:  # pragma: no cover - RETURNING always yields a row
        raise RuntimeError("INSERT ... RETURNING returned no row")
    return int(row[0])


async def finish_run(
    conn: AsyncConnection[Any],
    run_id: int,
    *,
    status: str,
    stats: RunStats,
    latency_ms: int,
    error_message: str | None = None,
) -> None:
    """Mark a run as success or failed and store its counts."""
    await conn.execute(
        """
        UPDATE ops.ingestion_runs
        SET finished_at         = now(),
            status              = %(status)s,
            source_version      = %(source_version)s,
            source_last_updated = %(source_last_updated)s,
            records_fetched     = %(fetched)s,
            records_inserted    = %(inserted)s,
            records_duplicate   = %(duplicate)s,
            records_rejected    = %(rejected)s,
            not_modified        = %(not_modified)s,
            rejection_reasons   = %(rejection_reasons)s,
            latency_ms          = %(latency_ms)s,
            error_message       = %(error_message)s
        WHERE run_id = %(run_id)s
        """,
        {
            "run_id": run_id,
            "status": status,
            "source_version": stats.source_version,
            "source_last_updated": stats.source_last_updated,
            "fetched": stats.fetched,
            "inserted": stats.inserted,
            "duplicate": stats.duplicate,
            "rejected": stats.rejected,
            "not_modified": stats.not_modified,
            "rejection_reasons": Jsonb(stats.rejection_reasons),
            "latency_ms": latency_ms,
            "error_message": error_message,
        },
    )


async def insert_station_status(
    conn: AsyncConnection[Any],
    records: Sequence[StationStatus],
    *,
    fetched_at: datetime,
    run_id: int,
) -> int:
    """Insert station reports, skipping (station_id, last_reported) pairs already stored.

    Returns the number of rows actually inserted.
    """
    if not records:
        return 0
    cursor = await conn.execute(
        """
        INSERT INTO raw.station_status (
            station_id, last_reported, fetched_at, ingestion_run_id,
            num_bikes_available, num_ebikes_available, num_bikes_disabled,
            num_docks_available, num_docks_disabled,
            is_installed, is_renting, is_returning
        )
        SELECT
            u.station_id, u.last_reported, %(fetched_at)s, %(run_id)s,
            u.bikes, u.ebikes, u.bikes_disabled, u.docks, u.docks_disabled,
            u.is_installed, u.is_renting, u.is_returning
        FROM unnest(
            %(station_id)s::text[], %(last_reported)s::timestamptz[],
            %(bikes)s::smallint[], %(ebikes)s::smallint[], %(bikes_disabled)s::smallint[],
            %(docks)s::smallint[], %(docks_disabled)s::smallint[],
            %(is_installed)s::boolean[], %(is_renting)s::boolean[], %(is_returning)s::boolean[]
        ) AS u(
            station_id, last_reported, bikes, ebikes, bikes_disabled, docks, docks_disabled,
            is_installed, is_renting, is_returning
        )
        ON CONFLICT (station_id, last_reported) DO NOTHING
        """,
        {
            "fetched_at": fetched_at,
            "run_id": run_id,
            "station_id": [r.station_id for r in records],
            "last_reported": [r.last_reported for r in records],
            "bikes": [r.num_bikes_available for r in records],
            "ebikes": [r.num_ebikes_available for r in records],
            "bikes_disabled": [r.num_bikes_disabled for r in records],
            "docks": [r.num_docks_available for r in records],
            "docks_disabled": [r.num_docks_disabled for r in records],
            "is_installed": [r.is_installed for r in records],
            "is_renting": [r.is_renting for r in records],
            "is_returning": [r.is_returning for r in records],
        },
    )
    return cursor.rowcount


@dataclass(frozen=True)
class UpsertResult:
    """How many rows an upsert created and how many it changed."""

    inserted: int
    updated: int


async def upsert_station_information(
    conn: AsyncConnection[Any],
    records: Sequence[StationInformation],
    *,
    seen_at: datetime,
    run_id: int,
) -> UpsertResult:
    """Insert new stations and update changed ones.

    last_seen_at always moves forward; updated_at moves only when an attribute changed,
    so dbt snapshots see real changes rather than every hourly poll.
    """
    if not records:
        return UpsertResult(inserted=0, updated=0)
    cursor = await conn.execute(
        """
        WITH incoming AS (
            SELECT *
            FROM unnest(
                %(station_id)s::text[], %(short_name)s::text[], %(name)s::text[],
                %(lat)s::float8[], %(lon)s::float8[], %(capacity)s::smallint[],
                %(region_id)s::text[], %(has_ebike_charging)s::boolean[]
            ) AS u(station_id, short_name, name, lat, lon, capacity, region_id,
                   has_ebike_charging)
        ),
        -- Evaluated against the table as it was before this statement.
        changed AS (
            SELECT i.station_id
            FROM incoming AS i
            JOIN raw.station_information AS t USING (station_id)
            WHERE (t.short_name, t.name, t.lat, t.lon, t.capacity, t.region_id,
                   t.has_ebike_charging)
                  IS DISTINCT FROM
                  (i.short_name, i.name, i.lat, i.lon, i.capacity, i.region_id,
                   i.has_ebike_charging)
        )
        INSERT INTO raw.station_information AS t (
            station_id, short_name, name, lat, lon, capacity, region_id,
            has_ebike_charging, first_seen_at, last_seen_at, updated_at, ingestion_run_id
        )
        SELECT i.station_id, i.short_name, i.name, i.lat, i.lon, i.capacity, i.region_id,
               i.has_ebike_charging, %(seen_at)s, %(seen_at)s, %(seen_at)s, %(run_id)s
        FROM incoming AS i
        ON CONFLICT (station_id) DO UPDATE SET
            short_name         = EXCLUDED.short_name,
            name               = EXCLUDED.name,
            lat                = EXCLUDED.lat,
            lon                = EXCLUDED.lon,
            capacity           = EXCLUDED.capacity,
            region_id          = EXCLUDED.region_id,
            has_ebike_charging = EXCLUDED.has_ebike_charging,
            last_seen_at       = EXCLUDED.last_seen_at,
            ingestion_run_id   = EXCLUDED.ingestion_run_id,
            updated_at = CASE
                WHEN t.station_id IN (SELECT station_id FROM changed)
                THEN EXCLUDED.updated_at
                ELSE t.updated_at
            END
        RETURNING
            (xmax = 0) AS was_inserted,
            (t.station_id IN (SELECT station_id FROM changed)) AS was_changed
        """,
        {
            "seen_at": seen_at,
            "run_id": run_id,
            "station_id": [r.station_id for r in records],
            "short_name": [r.short_name for r in records],
            "name": [r.name for r in records],
            "lat": [r.lat for r in records],
            "lon": [r.lon for r in records],
            "capacity": [r.capacity for r in records],
            "region_id": [r.region_id for r in records],
            "has_ebike_charging": [r.is_charging for r in records],
        },
    )
    rows = await cursor.fetchall()
    inserted = sum(1 for was_inserted, _ in rows if was_inserted)
    updated = sum(1 for was_inserted, was_changed in rows if not was_inserted and was_changed)
    return UpsertResult(inserted=inserted, updated=updated)


async def upsert_weather(
    conn: AsyncConnection[Any],
    records: Sequence[WeatherHour],
    *,
    fetched_at: datetime,
    run_id: int,
) -> int:
    """Insert or overwrite hourly weather. Returns the number of rows written."""
    if not records:
        return 0
    cursor = await conn.execute(
        """
        INSERT INTO raw.weather_hourly (
            observed_hour, temperature_c, apparent_temperature_c, precipitation_mm, rain_mm,
            snowfall_cm, weather_code, wind_speed_kmh, relative_humidity_pct, is_forecast,
            fetched_at, ingestion_run_id
        )
        SELECT u.*, %(fetched_at)s, %(run_id)s
        FROM unnest(
            %(observed_hour)s::timestamptz[], %(temperature_c)s::real[],
            %(apparent_temperature_c)s::real[], %(precipitation_mm)s::real[],
            %(rain_mm)s::real[], %(snowfall_cm)s::real[], %(weather_code)s::smallint[],
            %(wind_speed_kmh)s::real[], %(relative_humidity_pct)s::real[],
            %(is_forecast)s::boolean[]
        ) AS u
        ON CONFLICT (observed_hour) DO UPDATE SET
            temperature_c          = EXCLUDED.temperature_c,
            apparent_temperature_c = EXCLUDED.apparent_temperature_c,
            precipitation_mm       = EXCLUDED.precipitation_mm,
            rain_mm                = EXCLUDED.rain_mm,
            snowfall_cm            = EXCLUDED.snowfall_cm,
            weather_code           = EXCLUDED.weather_code,
            wind_speed_kmh         = EXCLUDED.wind_speed_kmh,
            relative_humidity_pct  = EXCLUDED.relative_humidity_pct,
            is_forecast            = EXCLUDED.is_forecast,
            fetched_at             = EXCLUDED.fetched_at,
            ingestion_run_id       = EXCLUDED.ingestion_run_id
        """,
        {
            "fetched_at": fetched_at,
            "run_id": run_id,
            "observed_hour": [r.observed_hour for r in records],
            "temperature_c": [r.temperature_c for r in records],
            "apparent_temperature_c": [r.apparent_temperature_c for r in records],
            "precipitation_mm": [r.precipitation_mm for r in records],
            "rain_mm": [r.rain_mm for r in records],
            "snowfall_cm": [r.snowfall_cm for r in records],
            "weather_code": [r.weather_code for r in records],
            "wind_speed_kmh": [r.wind_speed_kmh for r in records],
            "relative_humidity_pct": [r.relative_humidity_pct for r in records],
            "is_forecast": [r.is_forecast for r in records],
        },
    )
    return cursor.rowcount
