"""Jobs and schedules (all times New York local)."""

from __future__ import annotations

import dagster as dg
from dagster_dbt import build_dbt_asset_selection

from dockline_orchestration.assets import dockline_dbt_assets
from dockline_orchestration.checks import raw_freshness_checks

TIMEZONE = "America/New_York"

# Only one dbt build may run at a time (enforced by the run coordinator via this tag).
DBT_RUN_TAGS = {"dockline/dbt": "true"}

hourly_dbt_job = dg.define_asset_job(
    name="hourly_dbt_build",
    description="Staging, intermediate, station snapshot, dimensions, and 5-min/hourly facts.",
    # dbt tags are additive: daily models also inherit "hourly" from their folder.
    selection=build_dbt_asset_selection(
        [dockline_dbt_assets], dbt_select="tag:hourly", dbt_exclude="tag:daily"
    ),
    tags=DBT_RUN_TAGS,
)

live_dbt_job = dg.define_asset_job(
    name="live_dbt_build",
    description="The carried-forward 5-minute grid and 5-minute fact (Grafana rewind).",
    selection=build_dbt_asset_selection([dockline_dbt_assets], dbt_select="tag:live"),
    tags=DBT_RUN_TAGS,
)

daily_dbt_job = dg.define_asset_job(
    name="daily_dbt_build",
    description="Daily KPIs, the as-of KPI snapshot, and chronic problem stations.",
    selection=build_dbt_asset_selection([dockline_dbt_assets], dbt_select="tag:daily"),
    tags=DBT_RUN_TAGS,
)

raw_freshness_job = dg.define_asset_job(
    name="raw_freshness_checks",
    description="Checks that the ingestion service is still writing fresh rows.",
    selection=dg.AssetSelection.checks(*raw_freshness_checks),
)

hourly_schedule = dg.ScheduleDefinition(
    name="hourly_dbt_build_schedule",
    job=hourly_dbt_job,
    cron_schedule="5 * * * *",
    execution_timezone=TIMEZONE,
    default_status=dg.DefaultScheduleStatus.RUNNING,
)

live_schedule = dg.ScheduleDefinition(
    name="live_dbt_build_schedule",
    job=live_dbt_job,
    # Two minutes after each 5-minute bucket closes; skips :05 (the hourly build).
    cron_schedule="2,12,17,22,27,32,37,42,47,52,57 * * * *",
    execution_timezone=TIMEZONE,
    default_status=dg.DefaultScheduleStatus.RUNNING,
)

daily_schedule = dg.ScheduleDefinition(
    name="daily_dbt_build_schedule",
    job=daily_dbt_job,
    # After the 00:05 hourly build has closed the previous day's last hour.
    cron_schedule="30 0 * * *",
    execution_timezone=TIMEZONE,
    default_status=dg.DefaultScheduleStatus.RUNNING,
)

raw_freshness_schedule = dg.ScheduleDefinition(
    name="raw_freshness_checks_schedule",
    job=raw_freshness_job,
    cron_schedule="*/5 * * * *",
    execution_timezone=TIMEZONE,
    default_status=dg.DefaultScheduleStatus.RUNNING,
)
