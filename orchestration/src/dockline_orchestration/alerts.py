"""Failure alerts.

Every alert is (1) logged as a structured JSON line and (2) written to
``ops.pipeline_events``, which Grafana reads as an annotation source, so failures show
up as markers on the live dashboards.
"""

import json
from typing import Any, Literal

import dagster as dg
import structlog

from dockline_orchestration.resources import WarehouseResource

log = structlog.get_logger("dockline.alerts")

EventType = Literal["run_failure", "check_failure", "check_warning", "info"]
Severity = Literal["info", "warning", "critical"]


def record_pipeline_event(
    warehouse: WarehouseResource,
    *,
    event_type: EventType,
    severity: Severity,
    title: str,
    details: dict[str, Any] | None = None,
    dagster_run_id: str | None = None,
) -> None:
    """Log an operational event and store it in ops.pipeline_events."""
    payload = details or {}
    log.warning(
        "pipeline_event",
        event_type=event_type,
        severity=severity,
        title=title,
        dagster_run_id=dagster_run_id,
        **payload,
    )
    with warehouse.connect() as conn:
        conn.execute(
            """
            INSERT INTO ops.pipeline_events
                (source, event_type, severity, title, details, dagster_run_id)
            VALUES ('dagster', %s, %s, %s, %s::jsonb, %s)
            """,
            (event_type, severity, title, json.dumps(payload, default=str), dagster_run_id),
        )


@dg.run_failure_sensor(
    name="alert_on_run_failure",
    description="Logs every failed run and records it in ops.pipeline_events.",
    default_status=dg.DefaultSensorStatus.RUNNING,
    minimum_interval_seconds=30,
)
def alert_on_run_failure(context: dg.RunFailureSensorContext, warehouse: WarehouseResource) -> None:
    """Turn a failed Dagster run into an alert."""
    run = context.dagster_run
    record_pipeline_event(
        warehouse,
        event_type="run_failure",
        severity="critical",
        title=f"Dagster job {run.job_name} failed",
        details={"job_name": run.job_name, "error": context.failure_event.message},
        dagster_run_id=run.run_id,
    )
