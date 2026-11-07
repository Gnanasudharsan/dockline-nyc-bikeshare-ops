"""The Dagster code location for Dockline: ``dagster dev -m dockline_orchestration.definitions``."""

from __future__ import annotations

import dagster as dg
from dagster_dbt import DbtCliResource

from dockline_orchestration.alerts import alert_on_run_failure
from dockline_orchestration.assets import dockline_dbt_assets
from dockline_orchestration.checks import RAW_ASSET_SPECS, raw_freshness_checks
from dockline_orchestration.project import dbt_project
from dockline_orchestration.resources import WarehouseResource
from dockline_orchestration.schedules import (
    daily_dbt_job,
    daily_schedule,
    hourly_dbt_job,
    hourly_schedule,
    live_dbt_job,
    live_schedule,
    raw_freshness_job,
    raw_freshness_schedule,
)

defs = dg.Definitions(
    assets=[*RAW_ASSET_SPECS, dockline_dbt_assets],
    asset_checks=raw_freshness_checks,
    jobs=[live_dbt_job, hourly_dbt_job, daily_dbt_job, raw_freshness_job],
    schedules=[live_schedule, hourly_schedule, daily_schedule, raw_freshness_schedule],
    sensors=[alert_on_run_failure],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project),
        "warehouse": WarehouseResource(),
    },
)
