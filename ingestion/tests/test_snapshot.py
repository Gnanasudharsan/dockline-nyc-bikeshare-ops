"""Snapshot mode: certified KPIs from one GBFS poll, and the rolling history files.

``tests/fixtures/gbfs_parity`` holds a recorded poll (300 real stations plus edge
cases) and the expected output. The website's TypeScript implementation is checked
against the same expected output (web/test/metrics-parity.test.mjs).
Regenerate after an intended rule change with ``UPDATE_PARITY=1 uv run pytest``.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from dockline_ingestion import kpis
from dockline_ingestion.kpis import compute_live, round_half_away_from_zero
from dockline_ingestion.snapshot import (
    bucket_start,
    build_snapshot,
    current_weather,
    load_weather_conditions,
    update_daily,
    update_history,
)

ROOT = Path(__file__).resolve().parents[2]
PARITY = ROOT / "tests" / "fixtures" / "gbfs_parity"
WEATHER_CODES = ROOT / "dbt" / "seeds" / "wmo_weather_codes.csv"


def load(name: str) -> Any:
    return json.loads((PARITY / name).read_text())


@pytest.fixture(scope="module")
def parity_output() -> dict[str, Any]:
    now = load("case.json")["now_epoch"]
    return compute_live(load("station_status.json"), load("station_information.json"), now)


def test_matches_the_shared_expected_output(parity_output: dict[str, Any]) -> None:
    expected_path = PARITY / "expected.json"
    if os.environ.get("UPDATE_PARITY") == "1":
        expected_path.write_text(json.dumps(parity_output, indent=1, sort_keys=True) + "\n")
    assert parity_output == json.loads(expected_path.read_text())


def test_edge_cases_follow_the_certified_rules(parity_output: dict[str, Any]) -> None:
    states = {s["station_id"]: s["imbalance_state"] for s in parity_output["stations"]}
    assert states["zz-empty"] == "starving"  # the newer of two reports wins (bikes = 0)
    assert states["zz-full"] == "flooding"
    assert states["zz-fill-0.2"] == "starving"  # fill <= 0.2 is inclusive
    assert states["zz-fill-0.8"] == "flooding"  # fill >= 0.8 is inclusive
    assert states["zz-no-slots"] == "starving"
    assert states["zz-stale-1800"] == "balanced"  # 30 minutes is still in service
    assert states["zz-stale-1801"] == "offline"
    assert states["zz-not-installed"] == "offline"
    assert states["zz-closed"] == "offline"
    assert states["zz-return-only"] == "starving"
    assert states["zz-int-flags"] == "balanced"
    assert states["zz-sentinel"] == "offline"  # last_reported = 86400 placeholder
    assert states["zz-future"] == "offline"  # implausible timestamp rejected
    assert states["zz-info-only"] == "offline"
    assert "zz-status-only" not in states  # unlisted stations are not on the map


def test_rebalancing_rounds_halves_away_from_zero() -> None:
    assert round_half_away_from_zero(3.5) == 4
    assert round_half_away_from_zero(2.5) == 3  # Python's round() would give 2
    assert round_half_away_from_zero(-2.5) == -3


def test_thresholds_match_dbt_and_typescript() -> None:
    dbt_vars = yaml.safe_load((ROOT / "dbt" / "dbt_project.yml").read_text())["vars"]
    typescript = (ROOT / "web" / "src" / "lib" / "metrics.ts").read_text()
    for name, value in {
        "STALE_REPORT_MINUTES": kpis.STALE_REPORT_MINUTES,
        "TARGET_FILL_RATIO": kpis.TARGET_FILL_RATIO,
        "STARVING_FILL_RATIO": kpis.STARVING_FILL_RATIO,
        "FLOODING_FILL_RATIO": kpis.FLOODING_FILL_RATIO,
    }.items():
        assert dbt_vars[name.lower()] == value, name
        match = re.search(rf"export const {name} = ([0-9.]+);", typescript)
        assert match and float(match.group(1)) == value, name


def _live(as_of: str, states: dict[str, str], empty: int = 1) -> dict[str, Any]:
    kpi_values = {
        "as_of": as_of,
        "bikes_available": 10,
        "ebikes_available": 2,
        "docks_available": 10,
        "fill_ratio": 0.5,
        "stations_in_service": 4,
        "available_stations": 3,
        "empty_stations": empty,
        "full_stations": 0,
        "starving_stations": 1,
        "balanced_stations": 1,
        "flooding_stations": 1,
        "offline_stations": 1,
        "rebalance_need_bikes": 5,
    }
    stations = [{"station_id": sid, "imbalance_state": state} for sid, state in states.items()]
    return {"kpis": kpi_values, "stations": stations}


def test_history_appends_replaces_and_pads_new_stations() -> None:
    t0 = 1_794_000_000 - 1_794_000_000 % 600
    first = update_history(None, _live("x", {"a": "starving"}), t0)
    second = update_history(first, _live("x", {"a": "balanced", "b": "flooding"}), t0 + 600)
    assert second["frames"] == [kpis.iso_utc(t0), kpis.iso_utc(t0 + 600)]
    assert second["stations"] == {"a": "sb", "b": "-f"}
    # A second run in the same bucket replaces that frame instead of adding one.
    again = update_history(second, _live("x", {"a": "offline"}, empty=7), t0 + 600)
    assert again["stations"] == {"a": "so"}  # "b" has no data left in the window
    assert again["series"]["empty_stations"] == [1, 7]
    assert len(again["frames"]) == 2


def test_history_keeps_only_24_hours() -> None:
    t0 = 1_794_000_000 - 1_794_000_000 % 600
    history = None
    for step in range(150):
        history = update_history(history, _live("x", {"a": "balanced"}), t0 + step * 600)
    assert history is not None
    assert len(history["frames"]) == 144
    assert len(history["stations"]["a"]) == 144
    assert len(history["series"]["fill_ratio"]) == 144


def test_daily_counts_each_bucket_once() -> None:
    t0 = 1_794_000_000 - 1_794_000_000 % 600
    daily = update_daily(None, _live("x", {}), t0)
    daily = update_daily(daily, _live("x", {}), t0)  # same bucket: ignored
    daily = update_daily(daily, _live("x", {}, empty=3), t0 + 600)
    (day,) = daily["days"]
    assert day["samples"] == 2
    assert day["availability_rate"] == pytest.approx(6 / 8)
    assert day["empty_station_minutes"] == (1 + 3) * 10
    assert day["max_empty_stations"] == 3


def test_weather_condition_comes_from_the_dbt_seed() -> None:
    conditions = load_weather_conditions(WEATHER_CODES)
    hour = 1_794_000_000 - 1_794_000_000 % 3600
    payload = {
        "hourly": {
            "time": [hour],
            "temperature_2m": [9.5],
            "apparent_temperature": [7.0],
            "precipitation": [1.2],
            "rain": [1.2],
            "snowfall": [0.0],
            "weather_code": [61],
            "wind_speed_10m": [10.0],
            "relative_humidity_2m": [80.0],
        }
    }
    weather = current_weather(payload, hour + 120, conditions)
    assert weather is not None
    assert weather["condition"] == conditions[61] == "Rain"
    assert current_weather(None, hour, conditions) is None


def test_build_snapshot_writes_three_compact_files(tmp_path: Path) -> None:
    now = load("case.json")["now_epoch"]
    latest = build_snapshot(
        tmp_path,
        load("station_status.json"),
        load("station_information.json"),
        None,
        now,
        WEATHER_CODES,
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "daily-kpis.json",
        "history-24h.json",
        "latest.json",
    ]
    history = json.loads((tmp_path / "history-24h.json").read_text())
    assert history["frames"] == [kpis.iso_utc(bucket_start(now))]
    assert latest["kpis"]["stations"] == len(history["stations"])
    assert "\n" not in (tmp_path / "latest.json").read_text().strip()  # one compact line
