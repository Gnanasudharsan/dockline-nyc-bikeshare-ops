"""Integration tests: dbt build, freshness checks, and alerts against a real TimescaleDB."""

import json
from collections.abc import Iterator
from pathlib import Path

import dagster as dg
import psycopg
import pytest
from dbt.cli.main import dbtRunner
from psycopg.conninfo import conninfo_to_dict

from dockline_orchestration.alerts import record_pipeline_event
from dockline_orchestration.checks import RAW_ASSET_SPECS, raw_freshness_checks
from dockline_orchestration.project import DBT_PROJECT_DIR
from dockline_orchestration.resources import WarehouseResource
from dockline_orchestration.schedules import raw_freshness_job

pytestmark = pytest.mark.integration

# Monday 2026-11-02 09:00 New York = weekday morning peak.
AS_OF = "2026-11-02 14:00:00+00"

SEED_SQL = """
INSERT INTO ops.ingestion_runs (feed, started_at, finished_at, status)
VALUES ('station_status', '2026-11-02 12:00:00+00', '2026-11-02 12:00:01+00', 'success');

INSERT INTO raw.station_information
    (station_id, short_name, name, lat, lon, capacity, region_id, has_ebike_charging,
     first_seen_at, last_seen_at, updated_at, ingestion_run_id)
VALUES
    ('A', '5329.03', 'City Hall', 40.7128, -74.0060, 20, '71', false,
     '2026-11-02 12:00:00+00', '2026-11-02 13:30:00+00', '2026-11-02 12:00:00+00', 1),
    ('B', '4300.01', 'Bedford Stuyvesant', 40.6872, -73.9418, 10, '71', false,
     '2026-11-02 12:00:00+00', '2026-11-02 13:30:00+00', '2026-11-02 12:00:00+00', 1),
    ('C', 'JC001', 'Grove St PATH', 40.7196, -74.0431, 10, '70', true,
     '2026-11-02 12:00:00+00', '2026-11-02 13:30:00+00', '2026-11-02 12:00:00+00', 1);

-- Every 10 minutes from 12:00 to 13:50 UTC. A drains to 0 bikes from 13:00, B stays
-- balanced, C fills up completely from 13:00.
INSERT INTO raw.station_status
    (station_id, last_reported, fetched_at, ingestion_run_id, num_bikes_available,
     num_ebikes_available, num_docks_available, num_bikes_disabled, num_docks_disabled,
     is_installed, is_renting, is_returning)
SELECT
    station_id,
    ts,
    ts + interval '30 seconds',
    1,
    bikes,
    0,
    capacity - bikes,
    0,
    0,
    true,
    true,
    true
FROM (
    SELECT
        s.station_id,
        s.capacity,
        ts,
        CASE
            WHEN s.station_id = 'A' THEN CASE WHEN ts >= '2026-11-02 13:00+00' THEN 0 ELSE 8 END
            WHEN s.station_id = 'B' THEN 5
            ELSE CASE WHEN ts >= '2026-11-02 13:00+00' THEN 10 ELSE 6 END
        END AS bikes
    FROM (VALUES ('A', 20), ('B', 10), ('C', 10)) AS s (station_id, capacity)
    CROSS JOIN generate_series(
        timestamptz '2026-11-02 12:00+00', timestamptz '2026-11-02 13:50+00', interval '10 minutes'
    ) AS ts
) AS reports;

INSERT INTO raw.weather_hourly
    (observed_hour, temperature_c, apparent_temperature_c, precipitation_mm, rain_mm,
     snowfall_cm, weather_code, wind_speed_kmh, relative_humidity_pct, is_forecast,
     fetched_at, ingestion_run_id)
SELECT h, 12.5, 11.0, 0, 0, 0, 1, 10, 60, false, '2026-11-02 13:59+00', 1
FROM generate_series(
    timestamptz '2026-11-02 12:00+00', timestamptz '2026-11-02 14:00+00', interval '1 hour'
) AS h;
"""


@pytest.fixture
def seeded_database(migrated_database: str) -> str:
    with psycopg.connect(migrated_database, autocommit=True) as conn:
        conn.execute(SEED_SQL)
    return migrated_database


@pytest.fixture
def warehouse(seeded_database: str) -> WarehouseResource:
    params = conninfo_to_dict(seeded_database)
    return WarehouseResource(
        host=str(params["host"]),
        port=int(str(params["port"])),
        user=str(params["user"]),
        password=str(params["password"]),
        dbname=str(params["dbname"]),
    )


@pytest.fixture
def dbt_env(warehouse: WarehouseResource, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("POSTGRES_HOST", warehouse.host)
    monkeypatch.setenv("POSTGRES_PORT", str(warehouse.port))
    monkeypatch.setenv("POSTGRES_USER", warehouse.user)
    monkeypatch.setenv("POSTGRES_PASSWORD", warehouse.password)
    monkeypatch.setenv("POSTGRES_DB", warehouse.dbname)
    monkeypatch.setenv("DBT_TARGET", "dev")
    yield


def _dbt(args: list[str], tmp_path: Path) -> None:
    common = [
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROJECT_DIR),
    ]
    paths = ["--target-path", str(tmp_path / "target"), "--log-path", str(tmp_path / "logs")]
    result = dbtRunner().invoke([*args, *common, *paths])
    assert result.success, result.exception


def _rows(conninfo: str, query: str) -> list[tuple[object, ...]]:
    with psycopg.connect(conninfo) as conn:
        return conn.execute(query).fetchall()


def test_dbt_build_produces_star_schema(
    seeded_database: str, dbt_env: None, tmp_path: Path
) -> None:
    if not (DBT_PROJECT_DIR / "dbt_packages").exists():
        _dbt(["deps"], tmp_path)
    _dbt(["build", "--vars", json.dumps({"as_of": AS_OF})], tmp_path)

    # 3 stations x 24 five-minute buckets (12:00 .. 13:55 UTC).
    assert _rows(seeded_database, "SELECT count(*) FROM marts.fct_station_status_5min") == [(72,)]
    boroughs = _rows(
        seeded_database, "SELECT station_id, borough FROM marts.dim_station ORDER BY 1"
    )
    assert boroughs == [("A", "Manhattan"), ("B", "Brooklyn"), ("C", "Jersey City")]

    # A is empty for the 12 buckets from 13:00 (60 station-minutes), C is full.
    minutes = _rows(
        seeded_database,
        """
        SELECT station_id, sum(empty_minutes), sum(full_minutes), sum(in_service_minutes)
        FROM marts.fct_station_hourly GROUP BY 1 ORDER BY 1
        """,
    )
    assert minutes == [("A", 60, 0, 120), ("B", 0, 0, 120), ("C", 0, 60, 120)]

    board = _rows(
        seeded_database,
        """
        SELECT station_id, imbalance_state, recommended_action, rebalance_need_bikes
        FROM marts.mart_rebalancing_recommendations ORDER BY 1
        """,
    )
    assert board == [
        ("A", "starving", "Add bikes", 10),
        ("B", "balanced", "No action", 0),
        ("C", "flooding", "Remove bikes", -5),
    ]

    kpis = _rows(
        seeded_database,
        "SELECT borough, availability_rate FROM marts.fct_daily_kpis ORDER BY borough",
    )
    assert [borough for borough, _ in kpis] == ["Brooklyn", "Jersey City", "Manhattan"]
    assert ("Brooklyn", 1) in kpis

    chronic = _rows(
        seeded_database, "SELECT DISTINCT chronic_status FROM marts.mart_chronic_stations"
    )
    assert chronic == [("insufficient_data",)]

    # The Power BI model declares exactly the columns the bi views expose.
    assert_bi_views_match_power_bi_model(seeded_database)

    # A second (incremental) run is a no-op on the data.
    _dbt(["build", "--vars", json.dumps({"as_of": AS_OF})], tmp_path)
    assert _rows(seeded_database, "SELECT count(*) FROM marts.fct_station_status_5min") == [(72,)]


def test_record_pipeline_event(warehouse: WarehouseResource) -> None:
    record_pipeline_event(
        warehouse,
        event_type="run_failure",
        severity="critical",
        title="Dagster job test failed",
        details={"job_name": "test"},
        dagster_run_id="abc",
    )
    rows = _rows(
        warehouse.conninfo(),
        "SELECT source, event_type, severity, title, details->>'job_name', dagster_run_id "
        "FROM ops.pipeline_events",
    )
    assert rows == [
        ("dagster", "run_failure", "critical", "Dagster job test failed", "test", "abc")
    ]


def test_stale_raw_tables_fail_checks_and_raise_alerts(warehouse: WarehouseResource) -> None:
    # The seeded data is from 2026-11-02, so relative to the real clock every raw
    # table is stale.
    definitions = dg.Definitions(
        assets=RAW_ASSET_SPECS,
        asset_checks=raw_freshness_checks,
        jobs=[raw_freshness_job],
        resources={"warehouse": warehouse},
    )
    result = definitions.resolve_job_def("raw_freshness_checks").execute_in_process()
    evaluations = result.get_asset_check_evaluations()
    assert len(evaluations) == 3
    assert all(not evaluation.passed for evaluation in evaluations)
    assert all(evaluation.severity == dg.AssetCheckSeverity.ERROR for evaluation in evaluations)

    events = _rows(
        warehouse.conninfo(),
        "SELECT event_type, severity, title FROM ops.pipeline_events ORDER BY title",
    )
    assert events == [
        ("check_failure", "critical", "raw.station_information is stale"),
        ("check_failure", "critical", "raw.station_status is stale"),
        ("check_failure", "critical", "raw.weather_hourly is stale"),
    ]


POSTGRES_TO_TMDL = {
    "text": "string",
    "integer": "int64",
    "bigint": "int64",
    "smallint": "int64",
    "numeric": "double",
    "real": "double",
    "double precision": "double",
    "boolean": "boolean",
    "date": "dateTime",
    "timestamp without time zone": "dateTime",
}


def assert_bi_views_match_power_bi_model(conninfo: str) -> None:
    """Every TMDL column exists in its bi view with a compatible type, and vice versa."""
    import importlib.util
    import sys

    path = DBT_PROJECT_DIR.parent / "powerbi" / "build_pbip.py"
    spec = importlib.util.spec_from_file_location("build_pbip_for_test", path)
    assert spec and spec.loader
    build_pbip = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = build_pbip  # dataclasses need the module registered
    spec.loader.exec_module(build_pbip)
    rows = _rows(
        conninfo,
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'bi'",
    )
    database: dict[str, dict[str, str]] = {}
    for table, column, data_type in rows:
        database.setdefault(str(table), {})[str(column)] = POSTGRES_TO_TMDL[str(data_type)]
    for table in build_pbip.TABLES:
        model = {column.name: column.data_type for column in table.columns}
        assert model == database[table.view], table.name
