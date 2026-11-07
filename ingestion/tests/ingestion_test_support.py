"""Shared constants and helpers for ingestion tests (importable from test modules)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

FIXTURES = Path(__file__).parent / "fixtures"

DISCOVERY_URL = "https://gbfs.citibikenyc.com/gbfs/gbfs.json"
VERSIONS_URL = "https://gbfs.lyft.com/gbfs/1.1/bkn/en/gbfs_versions.json"
DISCOVERY_V2_3_URL = "https://gbfs.lyft.com/gbfs/2.3/bkn/gbfs.json"
STATUS_URL = "https://gbfs.lyft.com/gbfs/2.3/bkn/en/station_status.json"
INFORMATION_URL = "https://gbfs.lyft.com/gbfs/2.3/bkn/en/station_information.json"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def load_fixture(name: str) -> dict[str, Any]:
    """Load a recorded payload from tests/fixtures."""
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text())
    return payload


# ---------------------------------------------------------------- fixtures
# Re-exported by conftest.py so pytest registers them.


@pytest.fixture
def status_payload() -> dict[str, Any]:
    return load_fixture("station_status.json")


@pytest.fixture
def information_payload() -> dict[str, Any]:
    return load_fixture("station_information.json")


@pytest.fixture
def weather_payload() -> dict[str, Any]:
    return load_fixture("open_meteo_hourly.json")


@pytest.fixture
def status_fetched_at(status_payload: dict[str, Any]) -> datetime:
    """The moment the recorded station_status payload was fetched."""
    return datetime.fromtimestamp(status_payload["last_updated"], tz=UTC)


@pytest.fixture
def mocked_sources(respx_mock: respx.MockRouter) -> respx.MockRouter:
    """Serve every recorded payload at its real URL."""
    respx_mock.get(DISCOVERY_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("discovery_v1.json"))
    )
    respx_mock.get(VERSIONS_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("gbfs_versions.json"))
    )
    respx_mock.get(DISCOVERY_V2_3_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("discovery_v2_3.json"))
    )
    respx_mock.get(STATUS_URL, name="status").mock(
        return_value=httpx.Response(200, json=load_fixture("station_status.json"))
    )
    respx_mock.get(INFORMATION_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("station_information.json"))
    )
    respx_mock.get(url__startswith=OPEN_METEO_URL).mock(
        return_value=httpx.Response(200, json=load_fixture("open_meteo_hourly.json"))
    )
    return respx_mock
