from __future__ import annotations

import httpx
import pytest
import respx

from dockline_ingestion.sources import FeedDiscoveryError, GbfsClient, get_json, is_retryable
from ingestion_test_support import DISCOVERY_URL, STATUS_URL, load_fixture


async def test_resolves_preferred_version_from_discovery(mocked_sources: respx.MockRouter) -> None:
    async with httpx.AsyncClient() as http:
        feeds = await GbfsClient(http, DISCOVERY_URL, "2.3").resolve_feeds()
    assert feeds.version == "2.3"
    assert feeds.station_status == STATUS_URL
    assert "/2.3/" in feeds.station_information


async def test_falls_back_to_listed_feeds_when_version_unavailable(
    mocked_sources: respx.MockRouter,
) -> None:
    async with httpx.AsyncClient() as http:
        feeds = await GbfsClient(http, DISCOVERY_URL, "9.9").resolve_feeds()
    assert "/1.1/" in feeds.station_status


async def test_missing_required_feed_raises(respx_mock: respx.MockRouter) -> None:
    discovery = load_fixture("discovery_v2_3.json")
    discovery["data"]["en"]["feeds"] = [
        feed for feed in discovery["data"]["en"]["feeds"] if feed["name"] != "station_status"
    ]
    respx_mock.get(DISCOVERY_URL).mock(return_value=httpx.Response(200, json=discovery))
    async with httpx.AsyncClient() as http:
        with pytest.raises(FeedDiscoveryError, match="station_status"):
            await GbfsClient(http, DISCOVERY_URL, "2.3").resolve_feeds()


async def test_retries_server_errors_then_succeeds(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.ConnectError("boom"),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    async with httpx.AsyncClient() as http:
        body = await get_json(http, STATUS_URL, attempts=3, initial_wait_seconds=0)
    assert body == {"ok": True}
    assert route.call_count == 3


async def test_does_not_retry_client_errors(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(STATUS_URL).mock(return_value=httpx.Response(404))
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.HTTPStatusError):
            await get_json(http, STATUS_URL, attempts=3, initial_wait_seconds=0)
    assert route.call_count == 1


@pytest.mark.parametrize(
    ("status", "expected"), [(429, True), (500, True), (503, True), (400, False), (404, False)]
)
def test_retryable_statuses(status: int, expected: bool) -> None:
    request = httpx.Request("GET", STATUS_URL)
    error = httpx.HTTPStatusError(
        "x", request=request, response=httpx.Response(status, request=request)
    )
    assert is_retryable(error) is expected


async def test_conditional_fetch_sends_etag_and_handles_304(respx_mock: respx.MockRouter) -> None:
    route = respx_mock.get(STATUS_URL).mock(
        side_effect=[
            httpx.Response(200, json={"v": 1}, headers={"ETag": '"abc"'}),
            httpx.Response(304),
        ]
    )
    async with httpx.AsyncClient() as http:
        client = GbfsClient(http, DISCOVERY_URL, "2.3", attempts=1)
        assert await client.fetch_if_changed(STATUS_URL) == {"v": 1}
        assert await client.fetch_if_changed(STATUS_URL) is None
    assert "If-None-Match" not in route.calls[0].request.headers
    assert route.calls[1].request.headers["If-None-Match"] == '"abc"'
