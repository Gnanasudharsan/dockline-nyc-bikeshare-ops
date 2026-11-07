"""HTTP endpoints with fake Cube and LLM."""

from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from dockline_api.ask import AskService
from dockline_api.config import Settings
from dockline_api.limits import RateLimiter
from dockline_api.main import create_app


class StubCube:
    async def load(
        self, query: dict[str, Any], *, max_wait_seconds: float = 30.0
    ) -> list[dict[str, Any]]:
        if "dimensions" in query and "fleet_status.latitude" in query["dimensions"]:
            return [
                {
                    "fleet_status.station_id": "s1",
                    "fleet_status.station_name": "W 4 St",
                    "fleet_status.borough": "Manhattan",
                    "fleet_status.latitude": "40.73",
                    "fleet_status.longitude": "-74.00",
                    "fleet_status.imbalance_state": "starving",
                    "fleet_status.station_bikes_available": "0",
                    "fleet_status.station_docks_available": "20",
                }
            ]
        return [{member: "12" for member in query.get("measures", [])}]


class StubLLM:
    name = "stub"

    async def complete_json(
        self, system: str, user: str, *, effort: str = "medium"
    ) -> dict[str, Any]:
        if "<question>" in user:
            return {"supported": True, "topic": "live", "measures": ["empty_stations"]}
        return {"answer": "12 stations have no bikes right now."}


def client(per_minute: int = 6) -> TestClient:
    settings = Settings(cubejs_api_secret=SecretStr("test"), ask_rate_per_minute=per_minute)
    app = create_app(settings)
    test_client = TestClient(app)
    test_client.__enter__()
    app.state.cube = StubCube()
    app.state.ask = AskService(StubLLM(), app.state.cube, 300)
    app.state.limiter = RateLimiter(per_minute, 100)
    return test_client


def test_live_kpis() -> None:
    body = client().get("/v1/kpis/live").json()
    assert body["empty_stations"] == 12
    assert "as_of" in body


def test_stations_for_the_map() -> None:
    body = client().get("/v1/stations/live").json()
    assert body["count"] == 1
    assert body["stations"][0]["latitude"] == 40.73
    assert body["stations"][0]["imbalance_state"] == "starving"


def test_metrics_catalog() -> None:
    body = client().get("/v1/metrics").json()
    assert {topic["name"] for topic in body["topics"]} == {"live", "history", "chronic"}
    assert body["example_questions"]


def test_ask_end_to_end() -> None:
    body = client().post("/v1/ask", json={"question": "How many stations have no bikes?"}).json()
    assert body["status"] == "answered"
    assert body["answer"] == "12 stations have no bikes right now."
    assert body["metrics"][0]["definition"]


def test_ask_rejects_long_questions_and_rate_limits() -> None:
    test_client = client(per_minute=1)
    assert test_client.post("/v1/ask", json={"question": "x" * 400}).status_code == 422
    assert test_client.post("/v1/ask", json={"question": "How many bikes?"}).status_code == 429


def test_cors_allows_the_website_origin_only() -> None:
    test_client = client()
    allowed = test_client.options(
        "/v1/kpis/live",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    denied = test_client.options(
        "/v1/kpis/live",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers
