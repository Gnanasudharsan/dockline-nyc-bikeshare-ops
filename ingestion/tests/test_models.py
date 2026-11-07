from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from dockline_ingestion.models import (
    parse_open_meteo,
    parse_station_information,
    parse_station_status,
)


def test_recorded_status_payload_parses(
    status_payload: dict[str, Any], status_fetched_at: datetime
) -> None:
    batch = parse_station_status(status_payload, status_fetched_at)
    assert batch.fetched == 14
    assert len(batch.records) == 12
    assert batch.rejections == {"never_reported": 2}
    assert batch.ttl == 60
    assert batch.source_version == "2.3"
    first = batch.records[0]
    assert first.last_reported.tzinfo is not None
    assert isinstance(first.is_renting, bool)


def test_invalid_record_is_rejected_without_dropping_the_batch(
    status_payload: dict[str, Any], status_fetched_at: datetime
) -> None:
    payload = copy.deepcopy(status_payload)
    payload["data"]["stations"][0]["num_bikes_available"] = -3
    del payload["data"]["stations"][1]["station_id"]
    batch = parse_station_status(payload, status_fetched_at)
    assert batch.rejections["invalid"] == 2
    assert len(batch.records) == 10


def test_duplicate_report_in_one_payload_is_rejected(
    status_payload: dict[str, Any], status_fetched_at: datetime
) -> None:
    payload = copy.deepcopy(status_payload)
    payload["data"]["stations"].append(copy.deepcopy(payload["data"]["stations"][0]))
    batch = parse_station_status(payload, status_fetched_at)
    assert batch.rejections["duplicate"] == 1
    assert len(batch.records) == 12


def test_future_timestamp_is_rejected(
    status_payload: dict[str, Any], status_fetched_at: datetime
) -> None:
    payload = copy.deepcopy(status_payload)
    future = status_fetched_at + timedelta(hours=2)
    payload["data"]["stations"][0]["last_reported"] = int(future.timestamp())
    batch = parse_station_status(payload, status_fetched_at)
    assert batch.rejections["future_timestamp"] == 1


def test_missing_optional_counts_default_to_zero(
    status_payload: dict[str, Any], status_fetched_at: datetime
) -> None:
    payload = copy.deepcopy(status_payload)
    station = payload["data"]["stations"][0]
    station.pop("num_ebikes_available")
    station.pop("num_docks_disabled")
    batch = parse_station_status(payload, status_fetched_at)
    match = next(r for r in batch.records if r.station_id == station["station_id"])
    assert match.num_ebikes_available == 0
    assert match.num_docks_disabled == 0


def test_station_information_parses(information_payload: dict[str, Any]) -> None:
    batch = parse_station_information(information_payload)
    assert batch.fetched == 14
    assert len(batch.records) == 14
    assert batch.rejected == 0
    assert all(40 < record.lat < 41.5 for record in batch.records)


def test_station_information_rejects_missing_coordinates(
    information_payload: dict[str, Any],
) -> None:
    payload = copy.deepcopy(information_payload)
    del payload["data"]["stations"][0]["lat"]
    batch = parse_station_information(payload)
    assert batch.rejections == {"invalid": 1}


def test_open_meteo_splits_observed_and_forecast_hours(weather_payload: dict[str, Any]) -> None:
    hours = weather_payload["hourly"]["time"]
    midpoint = datetime.fromtimestamp(hours[len(hours) // 2], tz=UTC)
    batch = parse_open_meteo(weather_payload, fetched_at=midpoint)
    assert batch.fetched == len(hours)
    forecast = [record for record in batch.records if record.is_forecast]
    assert 0 < len(forecast) < len(hours)
    assert all(record.observed_hour > midpoint for record in forecast)


def test_open_meteo_rejects_ragged_arrays(weather_payload: dict[str, Any]) -> None:
    payload = copy.deepcopy(weather_payload)
    payload["hourly"]["rain"] = payload["hourly"]["rain"][:-1]
    with pytest.raises(ValueError, match="different lengths"):
        parse_open_meteo(payload, fetched_at=datetime.now(tz=UTC))
