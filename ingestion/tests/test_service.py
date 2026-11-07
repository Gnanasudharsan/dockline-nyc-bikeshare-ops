from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import psycopg
import pytest
import respx
from psycopg_pool import AsyncConnectionPool

from dockline_ingestion.config import Settings
from dockline_ingestion.healthcheck import is_healthy
from dockline_ingestion.service import IngestionService, next_status_delay
from dockline_ingestion.sources import GbfsClient, OpenMeteoClient
from ingestion_test_support import DISCOVERY_URL, OPEN_METEO_URL, STATUS_URL

# ---------------------------------------------------------------- unit


NOW = datetime(2026, 11, 7, 6, 20, 23, tzinfo=UTC)


@pytest.mark.parametrize(
    ("ttl", "updated_ago", "unchanged", "expected"),
    [
        # Fresh version published 1 s ago: wait until it expires + 5 s buffer.
        (60, 1.0, False, 64.0),
        # New version that is already 59 s old (the case that phase-locked): poll soon.
        (60, 59.0, False, 15.0),
        # Same version as last poll (304 or same last_updated): retry at the minimum.
        (60, 65.0, True, 15.0),
        # ttl 0 / missing means "no caching", not "poll in a tight loop": default 60 s.
        (0, 1.0, False, 64.0),
        (None, 1.0, False, 64.0),
        # Huge ttl clamped to the maximum.
        (3600, 1.0, False, 300.0),
    ],
)
def test_next_status_delay(
    ttl: int | None, updated_ago: float, unchanged: bool, expected: float
) -> None:
    delay = next_status_delay(
        ttl_seconds=ttl,
        source_last_updated=NOW - timedelta(seconds=updated_ago),
        unchanged=unchanged,
        now=NOW,
        minimum=15,
        maximum=300,
    )
    assert delay == pytest.approx(expected)


def test_next_status_delay_without_source_timestamp_uses_ttl() -> None:
    delay = next_status_delay(
        ttl_seconds=60,
        source_last_updated=None,
        unchanged=False,
        now=NOW,
        minimum=15,
        maximum=300,
    )
    assert delay == 60.0


def test_healthcheck_fresh_stale_and_missing(tmp_path: Path) -> None:
    heartbeat = tmp_path / "heartbeat"
    assert not is_healthy(heartbeat, max_age_seconds=180)
    heartbeat.touch()
    assert is_healthy(heartbeat, max_age_seconds=180)
    assert not is_healthy(heartbeat, max_age_seconds=180, now=time.time() + 600)


# ---------------------------------------------------------------- integration


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        postgres_password="unused",
        heartbeat_path=tmp_path / "heartbeat",
        min_status_poll_seconds=5,
    )


@pytest.fixture
async def pool(migrated_database: str) -> AsyncIterator[AsyncConnectionPool]:
    async with AsyncConnectionPool(
        migrated_database, min_size=1, max_size=3, open=False, kwargs={"autocommit": True}
    ) as opened:
        yield opened


@pytest.fixture
async def service(
    settings: Settings, pool: AsyncConnectionPool, status_fetched_at: datetime
) -> AsyncIterator[IngestionService]:
    async with httpx.AsyncClient() as http:
        yield IngestionService(
            settings=settings,
            pool=pool,
            gbfs=GbfsClient(http, DISCOVERY_URL, "2.3", attempts=1),
            weather=OpenMeteoClient(http, OPEN_METEO_URL, 40.71, -74.0, attempts=1),
            # Pin "now" to when the fixture was recorded so timestamps are plausible.
            clock=lambda: status_fetched_at,
        )


def query(conninfo: str, sql: str) -> list[tuple[object, ...]]:
    with psycopg.connect(conninfo) as conn:
        return conn.execute(sql).fetchall()


@pytest.mark.integration
async def test_end_to_end_poll_is_idempotent_and_audited(
    service: IngestionService,
    mocked_sources: respx.MockRouter,
    migrated_database: str,
    settings: Settings,
) -> None:
    assert await service.refresh_station_information()
    assert await service.poll_station_status()
    assert await service.poll_station_status()  # same payload again: nothing new
    assert await service.refresh_weather()

    assert query(migrated_database, "SELECT count(*) FROM raw.station_information") == [(14,)]
    assert query(migrated_database, "SELECT count(*) FROM raw.station_status") == [(12,)]
    assert query(
        migrated_database,
        "SELECT count(*) FROM (SELECT station_id, last_reported FROM raw.station_status "
        "GROUP BY 1, 2 HAVING count(*) > 1) d",
    ) == [(0,)]
    assert query(migrated_database, "SELECT count(*) > 0 FROM raw.weather_hourly") == [(True,)]

    runs = query(
        migrated_database,
        "SELECT feed, status, records_fetched, records_inserted, records_duplicate, "
        "records_rejected, rejection_reasons, source_version "
        "FROM ops.ingestion_runs WHERE feed = 'station_status' ORDER BY run_id",
    )
    assert runs == [
        ("station_status", "success", 14, 12, 0, 2, {"never_reported": 2}, "2.3"),
        ("station_status", "success", 14, 0, 12, 2, {"never_reported": 2}, "2.3"),
    ]
    assert is_healthy(settings.heartbeat_path, max_age_seconds=60)


@pytest.mark.integration
async def test_station_information_updates_only_on_real_change(
    service: IngestionService,
    mocked_sources: respx.MockRouter,
    migrated_database: str,
) -> None:
    await service.refresh_station_information()
    await service.refresh_station_information()
    runs = query(
        migrated_database,
        "SELECT records_inserted, records_duplicate FROM ops.ingestion_runs "
        "WHERE feed = 'station_information' ORDER BY run_id",
    )
    assert runs == [(14, 0), (0, 14)]


@pytest.mark.integration
async def test_failed_poll_is_recorded(
    service: IngestionService,
    mocked_sources: respx.MockRouter,
    migrated_database: str,
) -> None:
    await service.refresh_station_information()
    mocked_sources.routes["status"].mock(return_value=httpx.Response(500))
    assert not await service.poll_station_status()
    runs = query(
        migrated_database,
        "SELECT status, error_message LIKE 'HTTPStatusError%' FROM ops.ingestion_runs "
        "WHERE feed = 'station_status'",
    )
    assert runs == [("failed", True)]


@pytest.mark.integration
async def test_continuous_aggregates_answer_quickly(
    service: IngestionService,
    mocked_sources: respx.MockRouter,
    migrated_database: str,
) -> None:
    await service.refresh_station_information()
    await service.poll_station_status()
    with psycopg.connect(migrated_database, autocommit=True) as conn:
        conn.execute("CALL refresh_continuous_aggregate('agg.station_status_5min', NULL, NULL)")
        conn.execute("CALL refresh_continuous_aggregate('agg.station_status_hourly', NULL, NULL)")
        five_min = conn.execute(
            "SELECT count(DISTINCT station_id), sum(report_count) FROM agg.station_status_5min"
        ).fetchone()
        hourly = conn.execute(
            "SELECT count(DISTINCT station_id) FROM agg.station_status_hourly"
        ).fetchone()
    assert five_min == (12, 12)
    assert hourly == (12,)


@pytest.mark.integration
async def test_run_loop_stops_gracefully(
    service: IngestionService,
    mocked_sources: respx.MockRouter,
    migrated_database: str,
) -> None:
    stop = asyncio.Event()
    task = asyncio.create_task(service.run(stop))
    for _ in range(100):
        if mocked_sources.routes["status"].call_count >= 1:
            break
        await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=10)
    statuses = query(migrated_database, "SELECT DISTINCT status FROM ops.ingestion_runs ORDER BY 1")
    assert statuses == [("success",)], "no run may be left 'running' after shutdown"
    assert STATUS_URL in str(mocked_sources.routes["status"].calls.last.request.url)


@pytest.mark.integration
async def test_station_information_change_is_detected(
    service: IngestionService,
    mocked_sources: respx.MockRouter,
    migrated_database: str,
) -> None:
    from ingestion_test_support import INFORMATION_URL, load_fixture

    await service.refresh_station_information()
    renamed = load_fixture("station_information.json")
    renamed["data"]["stations"][0]["capacity"] = 99
    mocked_sources.get(INFORMATION_URL).mock(return_value=httpx.Response(200, json=renamed))
    await service.refresh_station_information()
    runs = query(
        migrated_database,
        "SELECT records_inserted, records_duplicate FROM ops.ingestion_runs "
        "WHERE feed = 'station_information' ORDER BY run_id",
    )
    assert runs == [(14, 0), (1, 13)]


@pytest.mark.integration
async def test_not_modified_poll_is_recorded_and_skips_parsing(
    service: IngestionService,
    mocked_sources: respx.MockRouter,
    migrated_database: str,
) -> None:
    from ingestion_test_support import load_fixture

    payload = load_fixture("station_status.json")

    def respond(request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, json=payload, headers={"ETag": '"v1"'})

    mocked_sources.routes["status"].mock(side_effect=respond)
    await service.refresh_station_information()
    assert await service.poll_station_status()
    assert await service.poll_station_status()
    runs = query(
        migrated_database,
        "SELECT not_modified, records_fetched, records_inserted FROM ops.ingestion_runs "
        "WHERE feed = 'station_status' ORDER BY run_id",
    )
    assert runs == [(False, 14, 12), (True, 0, 0)]
    second_request = mocked_sources.routes["status"].calls.last.request
    assert second_request.headers["If-None-Match"] == '"v1"'
