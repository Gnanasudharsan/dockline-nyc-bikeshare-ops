"""FastAPI app: live KPIs, a live KPI stream (SSE), stations for the map, and /ask.

Every number comes from Cube. Run with ``uvicorn --factory dockline_api.main:create_app``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dockline_api.ask import AskResponse, AskService, InputError, to_number
from dockline_api.catalog import SUGGESTED_QUESTIONS, TOPICS
from dockline_api.config import Settings
from dockline_api.cube import CubeClient, CubeError
from dockline_api.insights import InsightsResponse, all_findings
from dockline_api.limits import RateLimiter
from dockline_api.llm import build_llm

log = structlog.get_logger("dockline.api")

LIVE_MEASURES = [
    "bikes_available",
    "ebikes_available",
    "docks_available",
    "fill_ratio",
    "stations",
    "stations_in_service",
    "empty_stations",
    "full_stations",
    "starving_stations",
    "balanced_stations",
    "flooding_stations",
    "offline_stations",
    "rebalance_need_bikes",
    "data_freshness_seconds",
]


UNAVAILABLE_EVENT = json.dumps({"message": "Metrics are temporarily unavailable."})


class AskRequest(BaseModel):
    """Body of POST /v1/ask."""

    question: str = Field(min_length=1, max_length=1000)


STATE_CODES = {"starving": "s", "balanced": "b", "flooding": "f", "offline": "o"}


def encode_replay(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn (station, hour, state) rows into hour labels plus one state string per station."""
    hours = sorted({str(row["station_hourly.hour_start.hour"]) for row in rows})
    index = {hour: position for position, hour in enumerate(hours)}
    states: dict[str, list[str]] = {}
    for row in rows:
        station = str(row["station_hourly.station_id"])
        codes = states.setdefault(station, ["-"] * len(hours))
        codes[index[str(row["station_hourly.hour_start.hour"])]] = STATE_CODES.get(
            str(row["station_hourly.imbalance_state_end"]), "-"
        )
    return {
        "hours": [
            hour.replace(".000", "") + ("Z" if not hour.endswith("Z") else "") for hour in hours
        ],
        "legend": STATE_CODES,
        "stations": {station: "".join(codes) for station, codes in states.items()},
    }


def configure_logging(level: str) -> None:
    """JSON logs, like the other Dockline services."""
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app (settings are injectable for tests)."""
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as http:
            cube = CubeClient(
                http, settings.cube_api_url, settings.cubejs_api_secret.get_secret_value()
            )
            app.state.cube = cube
            app.state.ask = AskService(
                build_llm(settings, http), cube, settings.ask_max_question_chars
            )
            app.state.limiter = RateLimiter(settings.ask_rate_per_minute, settings.ask_daily_limit)
            yield

    app = FastAPI(
        title="Dockline API",
        version="0.5.0",
        description="Live operations intelligence for NYC bike share. Independent project; "
        "not affiliated with Citi Bike or Lyft. Uses the public GBFS feed.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    async def live_kpis(cube: CubeClient) -> dict[str, Any]:
        rows = await cube.load({"measures": [f"fleet_status.{m}" for m in LIVE_MEASURES]})
        values = {
            m: to_number(rows[0].get(f"fleet_status.{m}")) if rows else None for m in LIVE_MEASURES
        }
        return {"as_of": datetime.now(UTC).isoformat(timespec="seconds"), **values}

    @app.get("/health")
    async def health(request: Request) -> dict[str, str]:
        """Liveness plus a cheap Cube round trip."""
        try:
            await request.app.state.cube.load(
                {"measures": ["fleet_status.stations"]}, max_wait_seconds=5
            )
        except (CubeError, httpx.HTTPError):
            return {"status": "degraded", "cube": "unreachable"}
        return {"status": "ok", "cube": "ok"}

    @app.get("/v1/kpis/live")
    async def kpis_live(request: Request) -> dict[str, Any]:
        """Network KPIs right now (Cube fleet_status)."""
        try:
            return await live_kpis(request.app.state.cube)
        except (CubeError, httpx.HTTPError) as error:
            raise HTTPException(
                503, "Metrics are temporarily unavailable. Retry in a minute."
            ) from error

    @app.get("/v1/kpis/stream")
    async def kpis_stream(request: Request) -> StreamingResponse:
        """Server-Sent Events: a `kpis` event every SSE_INTERVAL_SECONDS."""

        async def events() -> AsyncIterator[str]:
            yield f"retry: {int(settings.sse_interval_seconds * 1000)}\n\n"
            while not await request.is_disconnected():
                try:
                    payload = await live_kpis(request.app.state.cube)
                    yield f"event: kpis\ndata: {json.dumps(payload)}\n\n"
                except (CubeError, httpx.HTTPError):
                    yield f"event: unavailable\ndata: {UNAVAILABLE_EVENT}\n\n"
                await asyncio.sleep(settings.sse_interval_seconds)

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/v1/stations/live")
    async def stations_live(request: Request) -> dict[str, Any]:
        """Every listed station with position and live state (for the website map)."""
        dimensions = [
            "station_id",
            "station_name",
            "borough",
            "latitude",
            "longitude",
            "imbalance_state",
            "station_bikes_available",
            "station_docks_available",
        ]
        try:
            rows = await request.app.state.cube.load(
                {"dimensions": [f"fleet_status.{d}" for d in dimensions], "limit": 5000}
            )
        except (CubeError, httpx.HTTPError) as error:
            raise HTTPException(
                503, "Stations are temporarily unavailable. Retry in a minute."
            ) from error
        stations = [
            {d: to_number(row.get(f"fleet_status.{d}")) for d in dimensions} for row in rows
        ]
        return {
            "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
            "count": len(stations),
            "stations": stations,
        }

    @app.get("/v1/stations/replay")
    async def stations_replay(request: Request) -> dict[str, Any]:
        """Each station's imbalance state at the end of each of the last 24 hours.

        Encoded compactly for the website: one character per hour per station
        (s = starving, b = balanced, f = flooding, o = offline, - = no data).
        """
        cube: CubeClient = request.app.state.cube
        rows: list[dict[str, Any]] = []
        try:
            # 4 windows of 6 hours keep each Cube response well under its row limit.
            for start, end in ((24, 18), (18, 12), (12, 6), (6, 0)):
                rows += await cube.load(
                    {
                        "measures": ["station_hourly.station_hours"],
                        "dimensions": [
                            "station_hourly.station_id",
                            "station_hourly.imbalance_state_end",
                        ],
                        "timeDimensions": [
                            {
                                "dimension": "station_hourly.hour_start",
                                "granularity": "hour",
                                "dateRange": f"from {start} hours ago to {end} hours ago"
                                if end
                                else f"from {start} hours ago to now",
                            }
                        ],
                        "limit": 20000,
                    }
                )
        except (CubeError, httpx.HTTPError) as error:
            raise HTTPException(
                503, "Replay is temporarily unavailable. Retry in a minute."
            ) from error
        return encode_replay(rows)

    @app.get("/v1/insights", response_model=InsightsResponse)
    async def insights(request: Request) -> InsightsResponse:
        """Return findings for the Insights page (live numbers, honest about missing history)."""
        try:
            return await all_findings(request.app.state.cube)
        except (CubeError, httpx.HTTPError) as error:
            raise HTTPException(
                503, "Insights are temporarily unavailable. Retry in a minute."
            ) from error

    @app.get("/v1/metrics")
    async def metrics() -> dict[str, Any]:
        """List the certified metrics Ask the Data can use, with definitions."""
        return {
            "topics": [
                {
                    "name": topic.name,
                    "description": topic.description,
                    "measures": [
                        {"name": m.name, "definition": m.definition, "unit": m.unit}
                        for m in topic.measures.values()
                    ],
                    "dimensions": [
                        {"name": d.name, "definition": d.definition}
                        for d in topic.dimensions.values()
                    ],
                    "time_ranges": list(topic.time_ranges),
                }
                for topic in TOPICS.values()
            ],
            "example_questions": list(SUGGESTED_QUESTIONS),
        }

    @app.post("/v1/ask", response_model=AskResponse)
    async def ask(body: AskRequest, request: Request) -> AskResponse:
        """Answer a question using only certified Cube metrics."""
        client = request.client.host if request.client else "unknown"
        if reason := request.app.state.limiter.check(client):
            raise HTTPException(429, reason)
        try:
            response: AskResponse = await request.app.state.ask.ask(body.question)
        except InputError as error:
            raise HTTPException(422, str(error)) from error
        return response

    return app
