"""Unit tests for the Dagster code location (no database needed)."""

from datetime import timedelta

import dagster as dg
import pytest

from dockline_orchestration.assets import (
    DAILY_MART_FRESHNESS,
    HOURLY_MART_FRESHNESS,
    freshness_policy_for,
)
from dockline_orchestration.checks import RAW_FRESHNESS_RULES, evaluate_freshness
from dockline_orchestration.definitions import defs


def _selected(job_name: str) -> set[str]:
    job = defs.resolve_job_def(job_name)
    return {key.to_user_string() for key in job.asset_layer.selected_asset_keys}


def test_definitions_load() -> None:
    dg.Definitions.validate_loadable(defs)


def test_raw_tables_are_lineage_roots() -> None:
    graph = defs.resolve_asset_graph()
    staging = graph.get(dg.AssetKey(["staging", "stg_gbfs__station_information"]))
    assert dg.AssetKey(["gbfs", "station_information"]) in staging.parent_keys


def test_hourly_job_builds_facts_but_not_daily_models() -> None:
    hourly = _selected("hourly_dbt_build")
    assert {
        "marts/fct_station_status_5min",
        "marts/fct_station_hourly",
        "marts/dim_station",
        "snapshots/snap_stations",
        "reference/nyc_neighborhoods",
    } <= hourly
    assert "marts/fct_daily_kpis" not in hourly
    assert "snapshots/snap_daily_kpis" not in hourly


def test_daily_job_builds_kpis_snapshot_and_chronic_stations() -> None:
    assert _selected("daily_dbt_build") == {
        "marts/fct_daily_kpis",
        "marts/mart_chronic_stations",
        "snapshots/snap_daily_kpis",
    }


@pytest.mark.parametrize(
    ("schedule_name", "cron"),
    [
        ("hourly_dbt_build_schedule", "5 * * * *"),
        ("daily_dbt_build_schedule", "30 0 * * *"),
        ("raw_freshness_checks_schedule", "*/5 * * * *"),
    ],
)
def test_schedules_run_by_default_in_new_york_time(schedule_name: str, cron: str) -> None:
    schedule = defs.resolve_schedule_def(schedule_name)
    assert schedule.cron_schedule == cron
    assert schedule.execution_timezone == "America/New_York"
    assert schedule.default_status == dg.DefaultScheduleStatus.RUNNING


def test_failure_sensor_is_running_by_default() -> None:
    sensor = defs.resolve_sensor_def("alert_on_run_failure")
    assert sensor.default_status == dg.DefaultSensorStatus.RUNNING


def test_freshness_policies_only_on_mart_tables() -> None:
    def props(fqn: list[str], tags: list[str], materialized: str = "table") -> dict[str, object]:
        return {
            "resource_type": "model",
            "fqn": fqn,
            "tags": tags,
            "config": {"materialized": materialized},
        }

    assert freshness_policy_for(props(["dockline", "marts", "core", "x"], ["hourly"])) == (
        HOURLY_MART_FRESHNESS
    )
    assert freshness_policy_for(props(["dockline", "marts", "core", "x"], ["hourly", "daily"])) == (
        DAILY_MART_FRESHNESS
    )
    assert freshness_policy_for(props(["dockline", "marts", "ops", "v"], [], "view")) is None
    assert freshness_policy_for(props(["dockline", "staging", "x"], ["hourly"])) is None


def test_every_mart_table_has_a_freshness_policy() -> None:
    graph = defs.resolve_asset_graph()
    for key in graph.get_all_asset_keys():
        node = graph.get(key)
        if key.path[0] == "marts" and key.path[-1] != "mart_rebalancing_recommendations":
            assert node.freshness_policy is not None, key


@pytest.mark.parametrize(
    ("lag", "passed", "severity"),
    [
        (timedelta(minutes=1), True, dg.AssetCheckSeverity.WARN),
        (timedelta(minutes=6), False, dg.AssetCheckSeverity.WARN),
        (timedelta(minutes=16), False, dg.AssetCheckSeverity.ERROR),
        (None, False, dg.AssetCheckSeverity.ERROR),
    ],
)
def test_evaluate_freshness(
    lag: timedelta | None, passed: bool, severity: dg.AssetCheckSeverity
) -> None:
    status_rule = RAW_FRESHNESS_RULES[0]
    assert evaluate_freshness(lag, status_rule) == (passed, severity)
