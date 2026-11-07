"""Pydantic models for source payloads and the parsing rules that turn them into rows.

Records are validated one at a time so a single malformed station never drops a whole
poll. Each rejected record is counted under a reason so ops.ingestion_runs can show
what was rejected and why.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Citi Bike launched in May 2013. Earlier timestamps are placeholders: inactive
# stations report last_reported = 86400 (1970-01-02).
EARLIEST_PLAUSIBLE_REPORT = datetime(2013, 1, 1, tzinfo=UTC)
# Allow a little clock skew between the feed and us before calling a report "future".
MAX_FUTURE_SKEW = timedelta(minutes=10)


class _Lenient(BaseModel):
    """Base model that ignores fields we do not store."""

    model_config = ConfigDict(extra="ignore", frozen=True)


# ---------------------------------------------------------------- GBFS discovery


class GbfsFeedRef(_Lenient):
    """One entry in a gbfs.json feed list."""

    name: str
    url: str


class GbfsLanguage(_Lenient):
    """The feeds published for one language."""

    feeds: list[GbfsFeedRef]


class GbfsDiscovery(_Lenient):
    """The gbfs.json auto-discovery file."""

    last_updated: datetime
    ttl: int = Field(ge=0)
    version: str | None = None
    data: dict[str, GbfsLanguage]


class GbfsVersionRef(_Lenient):
    """One entry in gbfs_versions.json."""

    version: str
    url: str


class GbfsVersionsData(_Lenient):
    """The data block of gbfs_versions.json."""

    versions: list[GbfsVersionRef]


class GbfsVersions(_Lenient):
    """The gbfs_versions.json file."""

    data: GbfsVersionsData


# ---------------------------------------------------------------- GBFS station feeds


class GbfsStationsData(_Lenient):
    """The data block of station_status / station_information.

    Stations stay raw dicts here so each one can be validated (and rejected) on its own.
    """

    stations: list[dict[str, Any]]


class GbfsStationFeed(_Lenient):
    """Envelope shared by station_status.json and station_information.json."""

    last_updated: datetime
    ttl: int = Field(ge=0)
    version: str | None = None
    data: GbfsStationsData


class StationStatus(_Lenient):
    """One station's live availability report."""

    station_id: str = Field(min_length=1)
    last_reported: datetime
    num_bikes_available: int = Field(ge=0, le=32_767)
    num_ebikes_available: int = Field(default=0, ge=0, le=32_767)
    num_bikes_disabled: int = Field(default=0, ge=0, le=32_767)
    num_docks_available: int = Field(ge=0, le=32_767)
    num_docks_disabled: int = Field(default=0, ge=0, le=32_767)
    is_installed: bool
    is_renting: bool
    is_returning: bool


class StationInformation(_Lenient):
    """One station's slowly changing attributes."""

    station_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    short_name: str | None = None
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    capacity: int | None = Field(default=None, ge=0, le=32_767)
    region_id: str | None = None
    is_charging: bool | None = None


# ---------------------------------------------------------------- Weather


@dataclass(frozen=True)
class WeatherHour:
    """One hour of NYC weather from Open-Meteo."""

    observed_hour: datetime
    temperature_c: float | None
    apparent_temperature_c: float | None
    precipitation_mm: float | None
    rain_mm: float | None
    snowfall_cm: float | None
    weather_code: int | None
    wind_speed_kmh: float | None
    relative_humidity_pct: float | None
    is_forecast: bool


class OpenMeteoHourly(_Lenient):
    """The hourly block of an Open-Meteo forecast response (timeformat=unixtime)."""

    time: list[int]
    temperature_2m: list[float | None]
    apparent_temperature: list[float | None]
    precipitation: list[float | None]
    rain: list[float | None]
    snowfall: list[float | None]
    weather_code: list[int | None]
    wind_speed_10m: list[float | None]
    relative_humidity_2m: list[float | None]


class OpenMeteoResponse(_Lenient):
    """An Open-Meteo forecast response."""

    hourly: OpenMeteoHourly


# ---------------------------------------------------------------- Parsing


@dataclass
class ParsedBatch[RecordT]:
    """Valid records from one poll, plus counts of what was rejected and why."""

    records: list[RecordT]
    fetched: int
    source_last_updated: datetime | None = None
    source_version: str | None = None
    ttl: int | None = None
    rejections: Counter[str] = field(default_factory=Counter)

    @property
    def rejected(self) -> int:
        """Total number of rejected records."""
        return sum(self.rejections.values())


def parse_station_status(
    payload: dict[str, Any], fetched_at: datetime
) -> ParsedBatch[StationStatus]:
    """Validate a station_status payload.

    Rejection reasons:
      invalid          the record failed schema validation
      never_reported   last_reported is a placeholder (station inactive)
      future_timestamp last_reported is implausibly far in the future
      duplicate        the same (station_id, last_reported) appeared twice in the payload
    """
    feed = GbfsStationFeed.model_validate(payload)
    batch: ParsedBatch[StationStatus] = ParsedBatch(
        records=[],
        fetched=len(feed.data.stations),
        source_last_updated=feed.last_updated,
        source_version=feed.version,
        ttl=feed.ttl,
    )
    seen: set[tuple[str, datetime]] = set()
    for raw_station in feed.data.stations:
        try:
            status = StationStatus.model_validate(raw_station)
        except ValidationError:
            batch.rejections["invalid"] += 1
            continue
        if status.last_reported < EARLIEST_PLAUSIBLE_REPORT:
            batch.rejections["never_reported"] += 1
            continue
        if status.last_reported > fetched_at + MAX_FUTURE_SKEW:
            batch.rejections["future_timestamp"] += 1
            continue
        key = (status.station_id, status.last_reported)
        if key in seen:
            batch.rejections["duplicate"] += 1
            continue
        seen.add(key)
        batch.records.append(status)
    return batch


def parse_station_information(payload: dict[str, Any]) -> ParsedBatch[StationInformation]:
    """Validate a station_information payload, rejecting invalid or repeated stations."""
    feed = GbfsStationFeed.model_validate(payload)
    batch: ParsedBatch[StationInformation] = ParsedBatch(
        records=[],
        fetched=len(feed.data.stations),
        source_last_updated=feed.last_updated,
        source_version=feed.version,
        ttl=feed.ttl,
    )
    seen: set[str] = set()
    for raw_station in feed.data.stations:
        try:
            info = StationInformation.model_validate(raw_station)
        except ValidationError:
            batch.rejections["invalid"] += 1
            continue
        if info.station_id in seen:
            batch.rejections["duplicate"] += 1
            continue
        seen.add(info.station_id)
        batch.records.append(info)
    return batch


def parse_open_meteo(payload: dict[str, Any], fetched_at: datetime) -> ParsedBatch[WeatherHour]:
    """Turn Open-Meteo's column arrays into one WeatherHour per hour."""
    hourly = OpenMeteoResponse.model_validate(payload).hourly
    columns: list[list[Any]] = [
        hourly.temperature_2m,
        hourly.apparent_temperature,
        hourly.precipitation,
        hourly.rain,
        hourly.snowfall,
        hourly.weather_code,
        hourly.wind_speed_10m,
        hourly.relative_humidity_2m,
    ]
    if any(len(column) != len(hourly.time) for column in columns):
        raise ValueError("Open-Meteo hourly arrays have different lengths")
    batch: ParsedBatch[WeatherHour] = ParsedBatch(records=[], fetched=len(hourly.time))
    for index, epoch_seconds in enumerate(hourly.time):
        observed_hour = datetime.fromtimestamp(epoch_seconds, tz=UTC)
        batch.records.append(
            WeatherHour(
                observed_hour=observed_hour,
                temperature_c=hourly.temperature_2m[index],
                apparent_temperature_c=hourly.apparent_temperature[index],
                precipitation_mm=hourly.precipitation[index],
                rain_mm=hourly.rain[index],
                snowfall_cm=hourly.snowfall[index],
                weather_code=hourly.weather_code[index],
                wind_speed_kmh=hourly.wind_speed_10m[index],
                relative_humidity_pct=hourly.relative_humidity_2m[index],
                is_forecast=observed_hour > fetched_at,
            )
        )
    return batch
