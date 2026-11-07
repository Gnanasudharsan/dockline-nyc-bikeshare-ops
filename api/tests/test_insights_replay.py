"""Replay encoding and the insight findings, with a stub Cube."""

from typing import Any

from dockline_api.insights import ebike_share, rebalancing_concentration, weather_effect
from dockline_api.main import encode_replay


def test_replay_encodes_one_character_per_hour_per_station() -> None:
    rows = [
        {
            "station_hourly.station_id": "a",
            "station_hourly.hour_start.hour": "2026-11-07T10:00:00.000",
            "station_hourly.imbalance_state_end": "starving",
        },
        {
            "station_hourly.station_id": "a",
            "station_hourly.hour_start.hour": "2026-11-07T11:00:00.000",
            "station_hourly.imbalance_state_end": "flooding",
        },
        {
            "station_hourly.station_id": "b",
            "station_hourly.hour_start.hour": "2026-11-07T11:00:00.000",
            "station_hourly.imbalance_state_end": "offline",
        },
    ]
    replay = encode_replay(rows)
    assert replay["hours"] == ["2026-11-07T10:00:00Z", "2026-11-07T11:00:00Z"]
    assert replay["stations"] == {"a": "sf", "b": "-o"}


class StubCube:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def load(
        self, query: dict[str, Any], *, max_wait_seconds: float = 30.0
    ) -> list[dict[str, Any]]:
        return self.rows


async def test_rebalancing_concentration_counts_the_top_decile() -> None:
    rows = [
        {"fleet_status.station_id": str(i), "fleet_status.bikes_to_move": str(n)}
        for i, n in enumerate([50] + [5] * 9)
    ]
    finding = await rebalancing_concentration(StubCube(rows))  # type: ignore[arg-type]
    assert finding.enough_data
    assert "top 1 (10%) account for 52.6% of the 95 bikes" in finding.finding


async def test_ebike_share_names_the_extremes() -> None:
    rows = [
        {
            "fleet_status.borough": "Bronx",
            "fleet_status.ebikes_available": "30",
            "fleet_status.bikes_available": "100",
        },
        {
            "fleet_status.borough": "Queens",
            "fleet_status.ebikes_available": "60",
            "fleet_status.bikes_available": "100",
        },
    ]
    finding = await ebike_share(StubCube(rows))  # type: ignore[arg-type]
    assert (
        finding.finding
        == "45.0% of bikes available right now are e-bikes, from 30.0% in Bronx to 60.0% in Queens."
    )


async def test_weather_waits_for_wet_and_dry_hours() -> None:
    rows = [
        {
            "weather.weather_condition": "Clear",
            "station_hourly.availability_rate": "0.9",
            "station_hourly.station_hours": "50000",
        }
    ]
    finding = await weather_effect(StubCube(rows))  # type: ignore[arg-type]
    assert not finding.enough_data
    assert "Clear" in finding.finding
