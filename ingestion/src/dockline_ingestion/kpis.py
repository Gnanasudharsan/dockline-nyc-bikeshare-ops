"""Point-in-time network KPIs computed straight from one GBFS poll (snapshot mode).

The full stack computes these in dbt and Cube (``fct_station_status_5min``,
``mart_rebalancing_recommendations``, the ``fleet_status`` cube). Snapshot mode has no
warehouse, so this module applies the same certified definitions (docs/metrics.md) to
a single station_status + station_information pair:

- in service: reported within the last 30 minutes, installed, and renting or returning
- fill_ratio = bikes / (bikes + docks), over in-service stations
- imbalance_state: offline if not in service; starving if bikes = 0 or fill <= 0.2;
  flooding if docks = 0 or fill >= 0.8; otherwise balanced
- rebalance_need = round(0.5 x (bikes + docks)) - bikes (half rounds away from zero);
  bikes to move = |rebalance_need| for starving and flooding stations
- empty: in service and bikes = 0; full: in service and docks = 0
- available: in service, renting, returning, >= 1 bike and >= 1 dock
- data_freshness_seconds = now - newest last_reported

The website's ``/api/live`` route implements the same rules in TypeScript
(``web/src/lib/metrics.ts``). Both are checked against one recorded fixture and one
expected output (``tests/fixtures/gbfs_parity``), so they cannot drift apart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dockline_ingestion.models import (
    StationInformation,
    StationStatus,
    parse_station_information,
    parse_station_status,
)

# The dbt vars behind the certified definitions (dbt/dbt_project.yml). A test keeps
# these, the dbt vars, and the TypeScript constants identical.
STALE_REPORT_MINUTES = 30
TARGET_FILL_RATIO = 0.5
STARVING_FILL_RATIO = 0.2
FLOODING_FILL_RATIO = 0.8


def iso_utc(epoch_seconds: int) -> str:
    """Format whole epoch seconds as ``YYYY-MM-DDTHH:MM:SSZ`` (same as the TypeScript side)."""
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def round_half_away_from_zero(value: float) -> int:
    """Round like PostgreSQL's ``round(numeric)``: halves go away from zero."""
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


@dataclass(frozen=True)
class StationState:
    """One listed station's live state."""

    station_id: str
    station_name: str
    latitude: float
    longitude: float
    imbalance_state: str
    bikes_available: int | None
    ebikes_available: int | None
    docks_available: int | None
    is_in_service: bool
    is_available: bool
    bikes_to_move: int


def classify_station(
    info: StationInformation, status: StationStatus | None, now_epoch: int
) -> StationState:
    """Apply the certified station rules to one station's latest report."""
    if status is None:
        in_service = False
    else:
        age_seconds = now_epoch - int(status.last_reported.timestamp())
        is_stale = age_seconds > STALE_REPORT_MINUTES * 60
        in_service = (
            not is_stale and status.is_installed and (status.is_renting or status.is_returning)
        )

    bikes = status.num_bikes_available if status else None
    docks = status.num_docks_available if status else None
    state = "offline"
    bikes_to_move = 0
    available = False
    if in_service and status is not None and bikes is not None and docks is not None:
        slots = bikes + docks
        fill = bikes / slots if slots else None
        if bikes == 0 or (fill is not None and fill <= STARVING_FILL_RATIO):
            state = "starving"
        elif docks == 0 or (fill is not None and fill >= FLOODING_FILL_RATIO):
            state = "flooding"
        else:
            state = "balanced"
        need = round_half_away_from_zero(TARGET_FILL_RATIO * slots) - bikes
        if state in ("starving", "flooding"):
            bikes_to_move = abs(need)
        available = status.is_renting and status.is_returning and bikes >= 1 and docks >= 1

    return StationState(
        station_id=info.station_id,
        station_name=info.name,
        latitude=info.lat,
        longitude=info.lon,
        imbalance_state=state,
        bikes_available=bikes,
        ebikes_available=status.num_ebikes_available if status else None,
        docks_available=docks,
        is_in_service=in_service,
        is_available=available,
        bikes_to_move=bikes_to_move,
    )


def latest_status_by_station(statuses: list[StationStatus]) -> dict[str, StationStatus]:
    """Keep each station's newest report (a payload may repeat a station)."""
    latest: dict[str, StationStatus] = {}
    for status in statuses:
        current = latest.get(status.station_id)
        if current is None or status.last_reported > current.last_reported:
            latest[status.station_id] = status
    return latest


def compute_live(
    status_payload: dict[str, Any], information_payload: dict[str, Any], now_epoch: int
) -> dict[str, Any]:
    """Return ``{"kpis": ..., "stations": [...]}`` for one poll, as served by /api/live.

    ``now_epoch`` is passed in (not read from the clock) so results are reproducible.
    """
    now = datetime.fromtimestamp(now_epoch, tz=UTC)
    status_batch = parse_station_status(status_payload, fetched_at=now)
    info_batch = parse_station_information(information_payload)
    statuses = latest_status_by_station(status_batch.records)

    listed = sorted(info_batch.records, key=lambda info: info.station_id)
    states = [classify_station(info, statuses.get(info.station_id), now_epoch) for info in listed]
    in_service = [s for s in states if s.is_in_service]

    bikes = sum(s.bikes_available or 0 for s in in_service)
    docks = sum(s.docks_available or 0 for s in in_service)
    reported = [
        int(statuses[s.station_id].last_reported.timestamp())
        for s in states
        if s.station_id in statuses
    ]
    feed_updated = status_batch.source_last_updated

    def count(state: str) -> int:
        return sum(1 for s in states if s.imbalance_state == state)

    kpis = {
        "as_of": iso_utc(now_epoch),
        "feed_updated_at": iso_utc(int(feed_updated.timestamp())) if feed_updated else None,
        "bikes_available": bikes,
        "ebikes_available": sum(s.ebikes_available or 0 for s in in_service),
        "docks_available": docks,
        "fill_ratio": bikes / (bikes + docks) if bikes + docks else None,
        "stations": len(states),
        "stations_in_service": len(in_service),
        "empty_stations": sum(1 for s in in_service if s.bikes_available == 0),
        "full_stations": sum(1 for s in in_service if s.docks_available == 0),
        "available_stations": sum(1 for s in states if s.is_available),
        "starving_stations": count("starving"),
        "balanced_stations": count("balanced"),
        "flooding_stations": count("flooding"),
        "offline_stations": count("offline"),
        "rebalance_need_bikes": sum(s.bikes_to_move for s in states),
        "data_freshness_seconds": now_epoch - max(reported) if reported else None,
    }
    stations = [
        {
            "station_id": s.station_id,
            "station_name": s.station_name,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "imbalance_state": s.imbalance_state,
            "station_bikes_available": s.bikes_available,
            "station_docks_available": s.docks_available,
        }
        for s in states
    ]
    return {"kpis": kpis, "stations": stations}
