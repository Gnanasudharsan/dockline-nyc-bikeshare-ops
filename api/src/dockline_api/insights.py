"""Findings for the website's Insights page, computed from Cube on request.

Each finding is a sentence with live numbers, a recommendation, and chart data. When
there is not enough history for a finding to mean anything, it says so instead of
drawing conclusions from a few hours of data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from dockline_api.ask import to_number
from dockline_api.cube import CubeClient

HISTORY_RANGE = "from 14 days ago to now"
MIN_STATION_HOURS = 20_000  # ~8 hours of the whole network


class Series(BaseModel):
    """One chart series."""

    name: str
    values: list[float | None]
    color: str  # a Dockline token name: signal, starving, flooding, balanced, offline, slate


class Chart(BaseModel):
    """Chart data the website renders with ECharts."""

    kind: str  # bar | column | line
    categories: list[str]
    series: list[Series]
    unit: str  # percent | count | bikes


class Finding(BaseModel):
    """One insight."""

    id: str
    title: str
    finding: str
    recommendation: str
    enough_data: bool
    chart: Chart | None = None
    basis: str  # what data the finding rests on


class InsightsResponse(BaseModel):
    """GET /v1/insights."""

    as_of: str
    findings: list[Finding]


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


async def _rows(cube: CubeClient, query: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {k.split(".")[-1]: to_number(v) for k, v in row.items()} for row in await cube.load(query)
    ]


async def empty_vs_full_by_borough(cube: CubeClient) -> Finding:
    """Some boroughs run out of bikes, others out of docks."""
    rows = await _rows(
        cube,
        {
            "measures": [
                "station_hourly.empty_share",
                "station_hourly.full_share",
                "station_hourly.station_hours",
            ],
            "dimensions": ["stations.borough"],
            "timeDimensions": [
                {"dimension": "station_hourly.hour_start", "dateRange": HISTORY_RANGE}
            ],
            "filters": [
                {"member": "stations.borough", "operator": "notEquals", "values": ["Unknown"]}
            ],
        },
    )
    rows.sort(key=lambda r: r["borough"])
    station_hours = sum(r["station_hours"] or 0 for r in rows)
    enough = station_hours >= MIN_STATION_HOURS and len(rows) >= 3
    chart = Chart(
        kind="bar",
        categories=[r["borough"] for r in rows],
        series=[
            Series(
                name="Empty (no bikes)", values=[r["empty_share"] for r in rows], color="starving"
            ),
            Series(
                name="Full (no docks)", values=[r["full_share"] for r in rows], color="flooding"
            ),
        ],
        unit="percent",
    )
    if not enough:
        return Finding(
            id="empty-vs-full",
            title="Empty or full: which problem each borough has",
            finding="Not enough history yet to compare boroughs fairly.",
            recommendation="Check back after a full day of data.",
            enough_data=False,
            chart=chart,
            basis=f"{station_hours:,} station-hours so far",
        )
    most_empty = max(rows, key=lambda r: r["empty_share"] or 0)
    most_full = max(rows, key=lambda r: r["full_share"] or 0)
    return Finding(
        id="empty-vs-full",
        title="Empty or full: which problem each borough has",
        finding=(
            f"{most_empty['borough']} spends the most time empty ({_pct(most_empty['empty_share'])} of "
            f"in-service station-minutes with no bike), while {most_full['borough']} spends the most time "
            f"full ({_pct(most_full['full_share'])} with no free dock)."
        ),
        recommendation=(
            f"Plan the two problems separately: in {most_full['borough']} the work is collecting bikes "
            f"from full stations; in {most_empty['borough']} it is restocking empty ones."
            if most_empty["borough"] != most_full["borough"]
            else f"{most_empty['borough']} needs both: restock its empty stations and collect bikes "
            "from its full ones, moving bikes within the borough where possible."
        ),
        enough_data=True,
        chart=chart,
        basis=f"{station_hours:,} station-hours over the last 14 days",
    )


async def hour_of_day(cube: CubeClient) -> Finding:
    """When in the day stations run out of bikes."""
    rows = await _rows(
        cube,
        {
            "measures": [
                "station_hourly.empty_share",
                "station_hourly.full_share",
                "station_hourly.station_hours",
            ],
            "dimensions": ["station_hourly.hour_of_day"],
            "timeDimensions": [
                {"dimension": "station_hourly.hour_start", "dateRange": HISTORY_RANGE}
            ],
        },
    )
    by_hour = {int(r["hour_of_day"]): r for r in rows}
    hours = list(range(24))
    labels = [f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}" for h in hours]
    chart = Chart(
        kind="column",
        categories=labels,
        series=[
            Series(
                name="Empty (no bikes)",
                values=[by_hour.get(h, {}).get("empty_share") for h in hours],
                color="starving",
            ),
            Series(
                name="Full (no docks)",
                values=[by_hour.get(h, {}).get("full_share") for h in hours],
                color="flooding",
            ),
        ],
        unit="percent",
    )
    covered = len(by_hour)
    if covered < 20:
        return Finding(
            id="hour-of-day",
            title="The hours when stations run dry",
            finding=f"Only {covered} of 24 hours have data so far, so the daily pattern is incomplete.",
            recommendation="Check back after a full day of data.",
            enough_data=False,
            chart=chart,
            basis=f"{covered} hours of the day observed",
        )
    worst = max(by_hour.values(), key=lambda r: r["empty_share"] or 0)
    best = min(by_hour.values(), key=lambda r: r["empty_share"] or 0)
    worst_label = labels[int(worst["hour_of_day"])]
    return Finding(
        id="hour-of-day",
        title="The hours when stations run dry",
        finding=(
            f"Stations are most often empty around {worst_label} ({_pct(worst['empty_share'])} of in-service "
            f"time), compared with {_pct(best['empty_share'])} at {labels[int(best['hour_of_day'])]}."
        ),
        recommendation=f"Finish restocking the emptiest stations before {worst_label}, not after riders find them empty.",
        enough_data=True,
        chart=chart,
        basis="all 24 local hours, last 14 days",
    )


async def rebalancing_concentration(cube: CubeClient) -> Finding:
    """How concentrated the current rebalancing need is."""
    rows = await _rows(
        cube,
        {
            "dimensions": ["fleet_status.station_id", "fleet_status.bikes_to_move"],
            "filters": [
                {"member": "fleet_status.bikes_to_move", "operator": "gt", "values": ["0"]}
            ],
            "limit": 5000,
        },
    )
    needs = sorted((float(r["bikes_to_move"]) for r in rows), reverse=True)
    total = sum(needs)
    if not needs or total == 0:
        return Finding(
            id="rebalancing-concentration",
            title="Where the rebalancing work is",
            finding="No station needs rebalancing right now.",
            recommendation="Nothing to do; check again later.",
            enough_data=False,
            basis="live state",
        )
    top_n = max(1, round(len(needs) * 0.1))
    top_share = sum(needs[:top_n]) / total
    deciles = []
    for decile in range(10):
        start, end = round(len(needs) * decile / 10), round(len(needs) * (decile + 1) / 10)
        deciles.append(sum(needs[start:end]) / total)
    chart = Chart(
        kind="column",
        categories=[f"{10 * d + 1}–{10 * (d + 1)}%" for d in range(10)],
        series=[Series(name="Share of bikes to move", values=deciles, color="signal")],
        unit="percent",
    )
    return Finding(
        id="rebalancing-concentration",
        title="Where the rebalancing work is",
        finding=(
            f"Right now {len(needs):,} stations need bikes added or removed, but the top {top_n} "
            f"(10%) account for {_pct(top_share)} of the {int(total):,} bikes to move."
        ),
        recommendation=f"Route trucks to the {top_n} highest-need stations first; the Rebalancing Board ranks them.",
        enough_data=True,
        chart=chart,
        basis="live state of every starving and flooding station",
    )


async def ebike_share(cube: CubeClient) -> Finding:
    """How much of the available fleet is electric, by borough."""
    rows = await _rows(
        cube,
        {
            "measures": ["fleet_status.ebikes_available", "fleet_status.bikes_available"],
            "dimensions": ["fleet_status.borough"],
            "filters": [
                {"member": "fleet_status.borough", "operator": "notEquals", "values": ["Unknown"]}
            ],
        },
    )
    rows = [r for r in rows if r["bikes_available"]]
    rows.sort(key=lambda r: r["borough"])
    shares = [r["ebikes_available"] / r["bikes_available"] for r in rows]
    total_e = sum(r["ebikes_available"] for r in rows)
    total = sum(r["bikes_available"] for r in rows)
    chart = Chart(
        kind="bar",
        categories=[r["borough"] for r in rows],
        series=[Series(name="E-bike share of bikes available", values=shares, color="signal")],
        unit="percent",
    )
    high = max(zip(rows, shares, strict=True), key=lambda pair: pair[1])
    low = min(zip(rows, shares, strict=True), key=lambda pair: pair[1])
    return Finding(
        id="ebike-share",
        title="How electric the available fleet is",
        finding=(
            f"{_pct(total_e / total)} of bikes available right now are e-bikes, from {_pct(low[1])} in "
            f"{low[0]['borough']} to {_pct(high[1])} in {high[0]['borough']}."
        ),
        recommendation=(
            f"Riders in {low[0]['borough']} have the fewest e-bikes to choose from; "
            "e-bike rebalancing could target it."
        ),
        enough_data=True,
        chart=chart,
        basis="live state",
    )


async def weather_effect(cube: CubeClient) -> Finding:
    """Availability by weather condition, only when several conditions were observed."""
    rows = await _rows(
        cube,
        {
            "measures": ["station_hourly.availability_rate", "station_hourly.station_hours"],
            "dimensions": ["weather.weather_condition"],
            "timeDimensions": [
                {"dimension": "station_hourly.hour_start", "dateRange": HISTORY_RANGE}
            ],
        },
    )
    usable = [r for r in rows if (r["station_hours"] or 0) >= 2_500]
    usable.sort(key=lambda r: r["weather_condition"])
    chart = Chart(
        kind="bar",
        categories=[r["weather_condition"] for r in rows],
        series=[
            Series(
                name="Availability rate",
                values=[r["availability_rate"] for r in rows],
                color="signal",
            )
        ],
        unit="percent",
    )
    wet = [
        r for r in usable if r["weather_condition"] in {"Rain", "Drizzle", "Snow", "Thunderstorm"}
    ]
    dry = [r for r in usable if r["weather_condition"] in {"Clear", "Cloudy"}]
    if not wet or not dry:
        seen = ", ".join(r["weather_condition"] for r in rows) or "none"
        return Finding(
            id="weather",
            title="Does bad weather change availability?",
            finding=f"Not enough weather variety yet to compare: conditions observed so far: {seen}.",
            recommendation="This finding fills in once both wet and dry hours have been observed.",
            enough_data=False,
            chart=chart,
            basis="station-hours by weather condition; a comparison needs both wet and dry hours",
        )
    wet_rate = sum(r["availability_rate"] * r["station_hours"] for r in wet) / sum(
        r["station_hours"] for r in wet
    )
    dry_rate = sum(r["availability_rate"] * r["station_hours"] for r in dry) / sum(
        r["station_hours"] for r in dry
    )
    direction = "higher" if wet_rate > dry_rate else "lower"
    return Finding(
        id="weather",
        title="Does bad weather change availability?",
        finding=(
            f"In wet hours, availability was {_pct(wet_rate)}, {direction} than {_pct(dry_rate)} in dry hours "
            "(fewer rides usually leave more stations balanced)."
        ),
        recommendation="On wet days, shift truck time from routine restocking to the stations that stay full.",
        enough_data=True,
        chart=chart,
        basis="station-hours by Open-Meteo condition, last 14 days",
    )


async def all_findings(cube: CubeClient) -> InsightsResponse:
    """Compute every finding."""
    findings = [
        await empty_vs_full_by_borough(cube),
        await hour_of_day(cube),
        await rebalancing_concentration(cube),
        await ebike_share(cube),
        await weather_effect(cube),
    ]
    return InsightsResponse(
        as_of=datetime.now(UTC).isoformat(timespec="seconds"), findings=findings
    )
