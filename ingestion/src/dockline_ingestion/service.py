"""The always-on ingestion loop.

Three independent jobs run on their own schedules:
  station_status       every feed ttl (about 60 s)
  station_information  hourly (also refreshes GBFS feed URLs)
  weather_hourly       hourly

Every run is recorded in ops.ingestion_runs, whether it succeeds or fails. A failing job
is logged and retried on its next tick; it never stops the other jobs.
On SIGTERM/SIGINT the loop lets in-flight jobs finish, then exits.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import structlog
from psycopg_pool import AsyncConnectionPool

from dockline_ingestion import repository
from dockline_ingestion.config import Settings
from dockline_ingestion.models import (
    parse_open_meteo,
    parse_station_information,
    parse_station_status,
)
from dockline_ingestion.repository import RunStats
from dockline_ingestion.sources import FeedUrls, GbfsClient, OpenMeteoClient

log = structlog.get_logger(__name__)

Clock = Callable[[], datetime]
SHUTDOWN_GRACE_SECONDS = 30.0
DISCOVERY_RETRY_SECONDS = 30.0


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(tz=UTC)


# Wait this long past the feed's expiry (last_updated + ttl) so the new version has
# reached the CDN before we ask for it.
PUBLISH_BUFFER_SECONDS = 5.0


def next_status_delay(
    *,
    ttl_seconds: int | None,
    source_last_updated: datetime | None,
    unchanged: bool,
    now: datetime,
    minimum: int,
    maximum: int,
) -> float:
    """Seconds to wait before the next station_status poll.

    GBFS data is valid until ``last_updated + ttl``, so the next poll is scheduled from
    the feed's own clock, not from when we happened to poll. A fixed 60 s timer can
    phase-lock just before the feed refreshes and keep reading the previous version.

    - New version received: wait until it expires, plus a small publish buffer.
    - Same version as last time (a 304, or the same ``last_updated``): the refresh has
      not reached the CDN yet, so check again after ``minimum`` seconds. These checks
      are conditional requests, so they cost the feed almost nothing.
    The result is always clamped to [minimum, maximum].
    """
    ttl = ttl_seconds if ttl_seconds and ttl_seconds > 0 else 60
    if source_last_updated is None:
        target = float(ttl)
    elif unchanged:
        target = float(minimum)
    else:
        expires_at = source_last_updated.timestamp() + ttl + PUBLISH_BUFFER_SECONDS
        target = expires_at - now.timestamp()
    return min(max(target, float(minimum)), float(maximum))


def touch_heartbeat(path: Path) -> None:
    """Record a successful station_status poll for the container healthcheck."""
    path.touch(exist_ok=True)


class IngestionService:
    """Owns the source clients and database pool, and runs the polling jobs."""

    def __init__(
        self,
        settings: Settings,
        pool: AsyncConnectionPool,
        gbfs: GbfsClient,
        weather: OpenMeteoClient,
        clock: Clock = utc_now,
    ) -> None:
        """Wire the service. The pool must use autocommit connections."""
        self._settings = settings
        self._pool = pool
        self._gbfs = gbfs
        self._weather = weather
        self._clock = clock
        self._feeds: FeedUrls | None = None
        self._last_status_ttl: int | None = None
        self._last_source_updated: datetime | None = None
        self._status_unchanged = False

    # ------------------------------------------------------------------ audit wrapper

    async def _audited(self, feed: str, job: Callable[[int], Awaitable[RunStats]]) -> bool:
        """Run ``job`` inside an ops.ingestion_runs record. Returns True on success."""
        started = time.perf_counter()
        async with self._pool.connection() as conn:
            run_id = await repository.start_run(conn, feed)
        try:
            stats = await job(run_id)
        except Exception as error:
            latency_ms = int((time.perf_counter() - started) * 1000)
            log.exception("ingestion_run_failed", feed=feed, run_id=run_id)
            async with self._pool.connection() as conn:
                await repository.finish_run(
                    conn,
                    run_id,
                    status="failed",
                    stats=RunStats(),
                    latency_ms=latency_ms,
                    error_message=f"{type(error).__name__}: {error}"[:2000],
                )
            return False
        latency_ms = int((time.perf_counter() - started) * 1000)
        async with self._pool.connection() as conn:
            await repository.finish_run(
                conn, run_id, status="success", stats=stats, latency_ms=latency_ms
            )
        log.info(
            "ingestion_run_succeeded",
            feed=feed,
            run_id=run_id,
            fetched=stats.fetched,
            inserted=stats.inserted,
            duplicate=stats.duplicate,
            rejected=stats.rejected,
            rejection_reasons=stats.rejection_reasons,
            latency_ms=latency_ms,
        )
        return True

    # ------------------------------------------------------------------ jobs

    async def _feed_urls(self) -> FeedUrls:
        if self._feeds is None:
            self._feeds = await self._gbfs.resolve_feeds()
        return self._feeds

    async def _station_status_job(self, run_id: int) -> RunStats:
        feeds = await self._feed_urls()
        payload = await self._gbfs.fetch_if_changed(feeds.station_status)
        if payload is None:
            self._status_unchanged = True
            return RunStats(
                not_modified=True,
                source_version=feeds.version,
                source_last_updated=self._last_source_updated,
            )
        fetched_at = self._clock()
        batch = parse_station_status(payload, fetched_at)
        self._last_status_ttl = batch.ttl
        self._status_unchanged = batch.source_last_updated == self._last_source_updated
        self._last_source_updated = batch.source_last_updated
        async with self._pool.connection() as conn, conn.transaction():
            inserted = await repository.insert_station_status(
                conn, batch.records, fetched_at=fetched_at, run_id=run_id
            )
        return RunStats(
            fetched=batch.fetched,
            inserted=inserted,
            duplicate=len(batch.records) - inserted,
            rejected=batch.rejected,
            rejection_reasons=dict(batch.rejections),
            source_version=batch.source_version or feeds.version,
            source_last_updated=batch.source_last_updated,
        )

    async def _station_information_job(self, run_id: int) -> RunStats:
        # Re-resolve discovery hourly so a moved feed is picked up without a restart.
        self._feeds = await self._gbfs.resolve_feeds()
        payload = await self._gbfs.fetch(self._feeds.station_information)
        seen_at = self._clock()
        batch = parse_station_information(payload)
        async with self._pool.connection() as conn, conn.transaction():
            result = await repository.upsert_station_information(
                conn, batch.records, seen_at=seen_at, run_id=run_id
            )
        return RunStats(
            fetched=batch.fetched,
            inserted=result.inserted + result.updated,
            duplicate=len(batch.records) - result.inserted - result.updated,
            rejected=batch.rejected,
            rejection_reasons=dict(batch.rejections),
            source_version=batch.source_version or self._feeds.version,
            source_last_updated=batch.source_last_updated,
        )

    async def _weather_job(self, run_id: int) -> RunStats:
        payload = await self._weather.fetch_hourly()
        fetched_at = self._clock()
        batch = parse_open_meteo(payload, fetched_at)
        async with self._pool.connection() as conn, conn.transaction():
            written = await repository.upsert_weather(
                conn, batch.records, fetched_at=fetched_at, run_id=run_id
            )
        return RunStats(fetched=batch.fetched, inserted=written, source_version="open-meteo")

    # ------------------------------------------------------------------ public runs

    async def poll_station_status(self) -> bool:
        """Poll station_status once; refresh the heartbeat on success."""
        ok = await self._audited("station_status", self._station_status_job)
        if ok:
            touch_heartbeat(self._settings.heartbeat_path)
        return ok

    async def refresh_station_information(self) -> bool:
        """Poll station_information once (and refresh feed URLs)."""
        return await self._audited("station_information", self._station_information_job)

    async def refresh_weather(self) -> bool:
        """Poll Open-Meteo once."""
        return await self._audited("weather_hourly", self._weather_job)

    # ------------------------------------------------------------------ loop

    async def _status_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await self.poll_station_status()
            delay = next_status_delay(
                ttl_seconds=self._last_status_ttl,
                source_last_updated=self._last_source_updated,
                unchanged=self._status_unchanged,
                now=utc_now(),
                minimum=self._settings.min_status_poll_seconds,
                maximum=self._settings.max_status_poll_seconds,
            )
            log.debug("next_status_poll", delay_seconds=round(delay, 1))
            await _sleep_or_stop(stop, delay)

    async def _fixed_interval_loop(
        self,
        stop: asyncio.Event,
        job: Callable[[], Awaitable[bool]],
        interval: int,
        *,
        initial_delay: float = 0.0,
    ) -> None:
        await _sleep_or_stop(stop, initial_delay)
        while not stop.is_set():
            await job()
            await _sleep_or_stop(stop, interval)

    async def run(self, stop: asyncio.Event) -> None:
        """Run every job until ``stop`` is set, then wait for in-flight work to finish."""
        while self._feeds is None and not stop.is_set():
            # Station information first: it resolves discovery and creates the stations
            # that status rows refer to.
            if not await self.refresh_station_information():
                await _sleep_or_stop(stop, DISCOVERY_RETRY_SECONDS)
        if stop.is_set():
            return
        tasks = [
            asyncio.create_task(self._status_loop(stop), name="station_status"),
            asyncio.create_task(
                self._fixed_interval_loop(
                    stop,
                    self.refresh_station_information,
                    self._settings.station_information_interval_seconds,
                    # It just ran during startup.
                    initial_delay=self._settings.station_information_interval_seconds,
                ),
                name="station_information",
            ),
            asyncio.create_task(
                self._fixed_interval_loop(
                    stop, self.refresh_weather, self._settings.weather_interval_seconds
                ),
                name="weather_hourly",
            ),
        ]
        await stop.wait()
        log.info("shutdown_requested", grace_seconds=SHUTDOWN_GRACE_SECONDS)
        _, pending = await asyncio.wait(tasks, timeout=SHUTDOWN_GRACE_SECONDS)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        log.info("shutdown_complete", cancelled=len(pending))


async def _sleep_or_stop(stop: asyncio.Event, seconds: float) -> None:
    """Sleep for ``seconds`` but wake immediately if ``stop`` is set."""
    if seconds <= 0:
        return
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except TimeoutError:
        return
