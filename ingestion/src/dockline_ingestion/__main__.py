"""Entry point: ``python -m dockline_ingestion``."""

from __future__ import annotations

import asyncio
import signal

import httpx
import structlog
from psycopg_pool import AsyncConnectionPool

from dockline_ingestion.config import Settings
from dockline_ingestion.logging_setup import configure_logging
from dockline_ingestion.service import IngestionService
from dockline_ingestion.sources import GbfsClient, OpenMeteoClient


async def run() -> None:
    """Start the service and run until SIGTERM or SIGINT."""
    settings = Settings()  # values come from the environment
    configure_logging(settings.log_level)
    log = structlog.get_logger("dockline_ingestion")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)

    timeout = httpx.Timeout(settings.http_timeout_seconds)
    headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
    async with (
        httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as http,
        AsyncConnectionPool(
            settings.conninfo(),
            min_size=1,
            max_size=4,
            open=False,
            kwargs={"autocommit": True},
        ) as pool,
    ):
        await pool.wait(timeout=60)
        log.info("ingestion_started", discovery_url=settings.gbfs_discovery_url)
        service = IngestionService(
            settings=settings,
            pool=pool,
            gbfs=GbfsClient(http, settings.gbfs_discovery_url, settings.gbfs_preferred_version),
            weather=OpenMeteoClient(
                http, settings.open_meteo_url, settings.nyc_latitude, settings.nyc_longitude
            ),
        )
        await service.run(stop)
    log.info("ingestion_stopped")


def main() -> None:
    """Run the service from the console."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
