"""HTTP clients for GBFS and Open-Meteo, with retries and GBFS feed discovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from dockline_ingestion.models import GbfsDiscovery, GbfsVersions

log = structlog.get_logger(__name__)

PREFERRED_LANGUAGE = "en"
REQUIRED_FEEDS = ("station_status", "station_information")


class FeedDiscoveryError(RuntimeError):
    """Raised when the GBFS discovery file does not list the feeds we need."""


def is_retryable(error: BaseException) -> bool:
    """Retry network failures, timeouts, rate limits, and server errors only.

    A 4xx other than 429 means our request is wrong, so retrying will not help.
    """
    if isinstance(error, httpx.TransportError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return False


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str] | None = None,
    attempts: int = 4,
    initial_wait_seconds: float = 1.0,
    max_wait_seconds: float = 20.0,
) -> dict[str, Any]:
    """GET ``url`` and return its JSON object, retrying transient failures with backoff."""
    retrying = AsyncRetrying(
        retry=retry_if_exception(is_retryable),
        stop=stop_after_attempt(attempts),
        wait=wait_exponential_jitter(multiplier=initial_wait_seconds, max=max_wait_seconds),
        reraise=True,
        before_sleep=lambda state: log.warning(
            "http_retry",
            url=url,
            attempt=state.attempt_number,
            error=repr(state.outcome.exception()) if state.outcome else None,
        ),
    )
    async for attempt in retrying:
        with attempt:
            response = await client.get(url, params=params)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError(f"Expected a JSON object from {url}")
            return body
    raise AssertionError("unreachable: tenacity re-raises the last error")  # pragma: no cover


@dataclass(frozen=True)
class FeedUrls:
    """The GBFS feed URLs resolved from auto-discovery."""

    version: str
    station_status: str
    station_information: str
    system_information: str | None


def _feeds_by_name(discovery: GbfsDiscovery) -> dict[str, str]:
    language = PREFERRED_LANGUAGE if PREFERRED_LANGUAGE in discovery.data else None
    if language is None:
        if not discovery.data:
            raise FeedDiscoveryError("Discovery file lists no languages")
        language = next(iter(discovery.data))
    return {feed.name: feed.url for feed in discovery.data[language].feeds}


class GbfsClient:
    """Resolves GBFS feed URLs from the auto-discovery file and fetches feeds."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        discovery_url: str,
        preferred_version: str,
        *,
        attempts: int = 4,
    ) -> None:
        """Create a client. ``attempts`` is the retry budget per request."""
        self._client = client
        self._discovery_url = discovery_url
        self._preferred_version = preferred_version
        self._attempts = attempts

    async def fetch(self, url: str) -> dict[str, Any]:
        """Fetch one GBFS feed as JSON."""
        return await get_json(self._client, url, attempts=self._attempts)

    async def resolve_feeds(self) -> FeedUrls:
        """Find current feed URLs, preferring the configured GBFS version (ADR 0005).

        Steps: read the discovery file; if it links gbfs_versions and that lists the
        preferred version, switch to that version's discovery file; then pick feeds.
        """
        discovery = GbfsDiscovery.model_validate(await self.fetch(self._discovery_url))
        feeds = _feeds_by_name(discovery)
        version = discovery.version or "1.0"

        versions_url = feeds.get("gbfs_versions")
        if versions_url and version != self._preferred_version:
            versions = GbfsVersions.model_validate(await self.fetch(versions_url))
            for candidate in versions.data.versions:
                if candidate.version.lstrip("v") == self._preferred_version:
                    discovery = GbfsDiscovery.model_validate(await self.fetch(candidate.url))
                    feeds = _feeds_by_name(discovery)
                    version = discovery.version or self._preferred_version
                    break

        missing = [name for name in REQUIRED_FEEDS if name not in feeds]
        if missing:
            raise FeedDiscoveryError(f"Discovery file is missing feeds: {missing}")
        resolved = FeedUrls(
            version=version,
            station_status=feeds["station_status"],
            station_information=feeds["station_information"],
            system_information=feeds.get("system_information"),
        )
        log.info("gbfs_feeds_resolved", version=resolved.version, url=resolved.station_status)
        return resolved


OPEN_METEO_HOURLY_VARIABLES = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "wind_speed_10m",
    "relative_humidity_2m",
)


class OpenMeteoClient:
    """Fetches hourly NYC weather: the last two days plus today's forecast."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        latitude: float,
        longitude: float,
        *,
        attempts: int = 4,
    ) -> None:
        """Create a client for one location."""
        self._client = client
        self._base_url = base_url
        self._params = {
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "hourly": ",".join(OPEN_METEO_HOURLY_VARIABLES),
            "past_days": "2",
            "forecast_days": "1",
            "timezone": "GMT",
            "timeformat": "unixtime",
        }
        self._attempts = attempts

    async def fetch_hourly(self) -> dict[str, Any]:
        """Return the raw Open-Meteo response."""
        return await get_json(
            self._client, self._base_url, params=self._params, attempts=self._attempts
        )
