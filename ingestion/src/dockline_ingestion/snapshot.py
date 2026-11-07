"""Snapshot mode: one poll of GBFS and Open-Meteo, written as compact JSON history.

Run by ``.github/workflows/snapshot.yml`` about every 10 minutes. It reads the files
from the previous run (if any), adds this run, and writes three files:

- ``latest.json``: this poll's KPIs and stations (``kpis.compute_live``) plus the
  current weather
- ``history-24h.json``: one frame per 10-minute bucket for the last 24 hours, with each
  station's imbalance state and the network KPIs
- ``daily-kpis.json``: per New York day, sums of sampled station states, for the last
  30 days

Usage: ``python -m dockline_ingestion.snapshot --dir <directory>``
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from dockline_ingestion.config import Settings
from dockline_ingestion.kpis import compute_live, iso_utc
from dockline_ingestion.models import parse_open_meteo
from dockline_ingestion.sources import GbfsClient, OpenMeteoClient

INTERVAL_MINUTES = 10
HISTORY_HOURS = 24
DAILY_DAYS = 30
NEW_YORK = ZoneInfo("America/New_York")
STATE_CODES = {"starving": "s", "balanced": "b", "flooding": "f", "offline": "o"}
NO_DATA = "-"
SERIES_KEYS = (
    "bikes_available",
    "ebikes_available",
    "docks_available",
    "fill_ratio",
    "empty_stations",
    "full_stations",
    "starving_stations",
    "balanced_stations",
    "flooding_stations",
    "offline_stations",
    "rebalance_need_bikes",
)
DEFAULT_WEATHER_CODES = Path("dbt/seeds/wmo_weather_codes.csv")


def bucket_start(now_epoch: int, minutes: int = INTERVAL_MINUTES) -> int:
    """Start of the ``minutes``-long UTC bucket containing ``now_epoch``."""
    return now_epoch - now_epoch % (minutes * 60)


def _parse_iso(value: str) -> int:
    return int(datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp())


def update_history(
    history: dict[str, Any] | None, live: dict[str, Any], bucket: int
) -> dict[str, Any]:
    """Add (or replace) the frame for ``bucket`` and keep only the last 24 hours."""
    frames: list[str] = list(history["frames"]) if history else []
    stations: dict[str, str] = dict(history["stations"]) if history else {}
    series: dict[str, list[Any]] = (
        {key: list(history["series"].get(key, [])) for key in SERIES_KEYS}
        if history
        else {key: [] for key in SERIES_KEYS}
    )
    frame = iso_utc(bucket)
    if frames and _parse_iso(frames[-1]) > bucket:
        return history or {}  # an older run finished late; keep the newer history
    replacing = bool(frames) and frames[-1] == frame
    if replacing:
        stations = {sid: codes[:-1] for sid, codes in stations.items()}
        series = {key: values[:-1] for key, values in series.items()}
    else:
        frames.append(frame)
    width = len(frames) - 1  # frames before this one

    current = {s["station_id"]: STATE_CODES[s["imbalance_state"]] for s in live["stations"]}
    for station_id, codes in stations.items():
        stations[station_id] = codes.ljust(width, NO_DATA)[:width] + current.get(
            station_id, NO_DATA
        )
    for station_id, code in current.items():
        if station_id not in stations:
            stations[station_id] = NO_DATA * width + code
    for key in SERIES_KEYS:
        series[key] = (series[key] + [None] * width)[:width] + [live["kpis"][key]]

    # Trim to the last 24 hours of buckets.
    cutoff = bucket - HISTORY_HOURS * 3600
    keep_from = next((i for i, f in enumerate(frames) if _parse_iso(f) > cutoff), len(frames))
    frames = frames[keep_from:]
    stations = {sid: codes[keep_from:] for sid, codes in stations.items()}
    stations = {sid: codes for sid, codes in sorted(stations.items()) if codes.strip(NO_DATA)}
    series = {key: values[keep_from:] for key, values in series.items()}
    return {
        "generated_at": live["kpis"]["as_of"],
        "interval_minutes": INTERVAL_MINUTES,
        "frames": frames,
        "legend": {**{code: state for state, code in STATE_CODES.items()}, NO_DATA: "no data"},
        "stations": stations,
        "series": series,
    }


def update_daily(daily: dict[str, Any] | None, live: dict[str, Any], bucket: int) -> dict[str, Any]:
    """Add this sample to its New York day; a bucket is counted at most once.

    Each sample stands for one 10-minute bucket, so station-minutes are estimated as
    sampled stations x 10. Missed workflow runs mean fewer samples, not wrong rates.
    """
    days: list[dict[str, Any]] = list(daily["days"]) if daily else []
    local_date = datetime.fromtimestamp(bucket, tz=UTC).astimezone(NEW_YORK).date().isoformat()
    day = next((d for d in days if d["date"] == local_date), None)
    if day is None:
        day = {
            "date": local_date,
            "samples": 0,
            "last_bucket": None,
            "in_service_samples": 0,
            "available_samples": 0,
            "empty_samples": 0,
            "full_samples": 0,
            "sum_bikes_available": 0,
            "sum_docks_available": 0,
            "max_empty_stations": 0,
            "max_full_stations": 0,
        }
        days.append(day)
    kpis = live["kpis"]
    if day["last_bucket"] != iso_utc(bucket):
        day["samples"] += 1
        day["last_bucket"] = iso_utc(bucket)
        day["in_service_samples"] += kpis["stations_in_service"]
        day["available_samples"] += kpis["available_stations"]
        day["empty_samples"] += kpis["empty_stations"]
        day["full_samples"] += kpis["full_stations"]
        day["sum_bikes_available"] += kpis["bikes_available"]
        day["sum_docks_available"] += kpis["docks_available"]
        day["max_empty_stations"] = max(day["max_empty_stations"], kpis["empty_stations"])
        day["max_full_stations"] = max(day["max_full_stations"], kpis["full_stations"])
    for entry in days:
        samples = entry["samples"] or 1
        entry["availability_rate"] = (
            entry["available_samples"] / entry["in_service_samples"]
            if entry["in_service_samples"]
            else None
        )
        entry["empty_station_minutes"] = entry["empty_samples"] * INTERVAL_MINUTES
        entry["full_station_minutes"] = entry["full_samples"] * INTERVAL_MINUTES
        entry["avg_bikes_available"] = round(entry["sum_bikes_available"] / samples)
        entry["avg_docks_available"] = round(entry["sum_docks_available"] / samples)
    days.sort(key=lambda d: d["date"])
    return {
        "generated_at": live["kpis"]["as_of"],
        "interval_minutes": INTERVAL_MINUTES,
        "days": days[-DAILY_DAYS:],
    }


def load_weather_conditions(path: Path) -> dict[int, str]:
    """WMO code -> condition, from the dbt seed that the full stack also uses."""
    with path.open(newline="") as handle:
        return {
            int(row["weather_code"]): row["weather_condition"] for row in csv.DictReader(handle)
        }


def current_weather(
    payload: dict[str, Any] | None, now_epoch: int, conditions: dict[int, str]
) -> dict[str, Any] | None:
    """Return the observed weather for the current UTC hour, or None if unavailable."""
    if payload is None:
        return None
    now = datetime.fromtimestamp(now_epoch, tz=UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    for record in parse_open_meteo(payload, fetched_at=now + timedelta(hours=1)).records:
        if record.observed_hour == hour:
            code = record.weather_code
            return {
                "observed_hour": iso_utc(int(hour.timestamp())),
                "temperature_c": record.temperature_c,
                "precipitation_mm": record.precipitation_mm,
                "weather_code": code,
                "condition": conditions.get(code, "Unknown") if code is not None else "Unknown",
            }
    return None


async def fetch_sources() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Fetch station status and information (required) and weather (optional)."""
    defaults = Settings.model_fields
    timeout = httpx.Timeout(20.0)
    headers = {
        "User-Agent": "dockline-snapshot (+https://github.com/Gnanasudharsan/dockline-nyc-bikeshare-ops)"
    }
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        gbfs = GbfsClient(
            client,
            str(defaults["gbfs_discovery_url"].default),
            str(defaults["gbfs_preferred_version"].default),
        )
        feeds = await gbfs.resolve_feeds()
        status, information = await asyncio.gather(
            gbfs.fetch(feeds.station_status), gbfs.fetch(feeds.station_information)
        )
        weather: dict[str, Any] | None
        try:
            weather = await OpenMeteoClient(
                client,
                str(defaults["open_meteo_url"].default),
                float(defaults["nyc_latitude"].default),
                float(defaults["nyc_longitude"].default),
            ).fetch_hourly()
        except (httpx.HTTPError, ValueError):
            weather = None  # weather is context, not a reason to skip a snapshot
    return status, information, weather


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n")
    temporary.replace(path)


def build_snapshot(
    directory: Path,
    status: dict[str, Any],
    information: dict[str, Any],
    weather_payload: dict[str, Any] | None,
    now_epoch: int,
    weather_codes: Path = DEFAULT_WEATHER_CODES,
) -> dict[str, Any]:
    """Compute this run's files from fetched payloads and the previous run's files."""
    live = compute_live(status, information, now_epoch)
    bucket = bucket_start(now_epoch)
    weather = current_weather(weather_payload, now_epoch, load_weather_conditions(weather_codes))
    latest = {"generated_at": live["kpis"]["as_of"], **live, "weather": weather}
    history = update_history(_read_json(directory / "history-24h.json"), live, bucket)
    daily = update_daily(_read_json(directory / "daily-kpis.json"), live, bucket)
    directory.mkdir(parents=True, exist_ok=True)
    _write_json(directory / "latest.json", latest)
    _write_json(directory / "history-24h.json", history)
    _write_json(directory / "daily-kpis.json", daily)
    return latest


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, required=True, help="where the JSON files live")
    parser.add_argument("--weather-codes", type=Path, default=DEFAULT_WEATHER_CODES)
    args = parser.parse_args()
    status, information, weather = asyncio.run(fetch_sources())
    latest = build_snapshot(
        args.dir, status, information, weather, int(time.time()), args.weather_codes
    )
    kpis = latest["kpis"]
    print(
        json.dumps(
            {
                "event": "snapshot_written",
                "as_of": kpis["as_of"],
                "stations": kpis["stations"],
                "empty_stations": kpis["empty_stations"],
                "data_freshness_seconds": kpis["data_freshness_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
