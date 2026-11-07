"""Freshness checks.

* **Raw feed freshness** (custom SQL, here): how old is the newest row the ingestion
  service wrote? Runs every 5 minutes. A failing check is also recorded as a pipeline
  event (alert).
* **Mart freshness** (Dagster freshness policies, see ``assets.py``): has dbt rebuilt
  the hourly and daily marts recently enough?
"""

from dataclasses import dataclass
from datetime import timedelta

import dagster as dg
from psycopg import sql

from dockline_orchestration.alerts import record_pipeline_event
from dockline_orchestration.resources import WarehouseResource


@dataclass(frozen=True)
class RawFreshnessRule:
    """How fresh one raw table must be.

    ``warn_after`` fails the check with WARN severity, ``error_after`` with ERROR.
    """

    asset_key: dg.AssetKey
    schema: str
    table: str
    loaded_at_column: str
    warn_after: timedelta
    error_after: timedelta
    description: str


RAW_FRESHNESS_RULES: tuple[RawFreshnessRule, ...] = (
    RawFreshnessRule(
        asset_key=dg.AssetKey(["gbfs", "station_status"]),
        schema="raw",
        table="station_status",
        loaded_at_column="fetched_at",
        warn_after=timedelta(minutes=5),
        error_after=timedelta(minutes=15),
        description="Station status rows are written roughly every minute.",
    ),
    RawFreshnessRule(
        asset_key=dg.AssetKey(["gbfs", "station_information"]),
        schema="raw",
        table="station_information",
        loaded_at_column="last_seen_at",
        warn_after=timedelta(hours=2),
        error_after=timedelta(hours=6),
        description="Station information is refreshed hourly.",
    ),
    RawFreshnessRule(
        asset_key=dg.AssetKey(["open_meteo", "weather_hourly"]),
        schema="raw",
        table="weather_hourly",
        loaded_at_column="fetched_at",
        warn_after=timedelta(hours=2),
        error_after=timedelta(hours=6),
        description="Weather is refreshed hourly.",
    ),
)

# The raw tables are written by the ingestion service, not by Dagster. Declaring them
# as external assets puts them at the root of the lineage graph and lets checks
# attach to them.
RAW_ASSET_SPECS = [
    dg.AssetSpec(
        key=rule.asset_key,
        group_name="raw",
        description=f"{rule.schema}.{rule.table}, loaded by dockline-ingestion. {rule.description}",
        kinds={"timescaledb"},
    )
    for rule in RAW_FRESHNESS_RULES
]


def evaluate_freshness(
    lag: timedelta | None, rule: RawFreshnessRule
) -> tuple[bool, dg.AssetCheckSeverity]:
    """Decide pass/fail and severity for a measured lag (None = table is empty)."""
    if lag is None or lag > rule.error_after:
        return False, dg.AssetCheckSeverity.ERROR
    if lag > rule.warn_after:
        return False, dg.AssetCheckSeverity.WARN
    return True, dg.AssetCheckSeverity.WARN


def _build_raw_freshness_check(rule: RawFreshnessRule) -> dg.AssetChecksDefinition:
    @dg.asset_check(
        asset=rule.asset_key,
        name="raw_freshness",
        description=(
            f"Newest {rule.loaded_at_column} must be under {rule.warn_after} old "
            f"(error after {rule.error_after})."
        ),
    )
    def _check(
        context: dg.AssetCheckExecutionContext, warehouse: WarehouseResource
    ) -> dg.AssetCheckResult:
        query = sql.SQL("SELECT now() - max({column}) FROM {table}").format(
            column=sql.Identifier(rule.loaded_at_column),
            table=sql.Identifier(rule.schema, rule.table),
        )
        with warehouse.connect() as conn:
            row = conn.execute(query).fetchone()
        lag = row[0] if row and isinstance(row[0], timedelta) else None
        passed, severity = evaluate_freshness(lag, rule)
        lag_seconds = round(lag.total_seconds()) if lag is not None else None
        if not passed:
            critical = severity == dg.AssetCheckSeverity.ERROR
            record_pipeline_event(
                warehouse,
                event_type="check_failure" if critical else "check_warning",
                severity="critical" if critical else "warning",
                title=f"{rule.schema}.{rule.table} is stale",
                details={"lag_seconds": lag_seconds, "table": f"{rule.schema}.{rule.table}"},
                dagster_run_id=context.run.run_id,
            )
        return dg.AssetCheckResult(
            passed=passed,
            severity=severity,
            metadata={
                "lag_seconds": dg.MetadataValue.int(lag_seconds or -1),
                "warn_after_seconds": int(rule.warn_after.total_seconds()),
                "error_after_seconds": int(rule.error_after.total_seconds()),
            },
        )

    return _check


raw_freshness_checks = [_build_raw_freshness_check(rule) for rule in RAW_FRESHNESS_RULES]
