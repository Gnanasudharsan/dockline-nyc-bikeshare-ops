from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import psycopg
import pytest

from dockline_warehouse.migrate import (
    DEFAULT_MIGRATIONS_DIR,
    MigrationError,
    discover_migrations,
    ensure_databases,
    ensure_role_password,
    extra_databases_from_env,
    migrate,
)

# ---------------------------------------------------------------- unit


def test_discovers_repository_migrations_in_order() -> None:
    migrations = discover_migrations(DEFAULT_MIGRATIONS_DIR)
    versions = [migration.version for migration in migrations]
    assert versions == sorted(versions)
    assert versions[0] == 1
    assert versions == list(range(1, len(versions) + 1)), "versions must have no gaps"


def test_continuous_aggregate_migrations_run_outside_a_transaction() -> None:
    for migration in discover_migrations(DEFAULT_MIGRATIONS_DIR):
        creates_cagg = "timescaledb.continuous" in migration.sql_text
        assert migration.runs_in_transaction is not creates_cagg, migration.path.name


def test_rejects_badly_named_file(tmp_path: Path) -> None:
    (tmp_path / "create_things.sql").write_text("SELECT 1;")
    with pytest.raises(MigrationError, match="0001_name.sql"):
        discover_migrations(tmp_path)


def test_rejects_duplicate_versions(tmp_path: Path) -> None:
    (tmp_path / "0001_a.sql").write_text("SELECT 1;")
    (tmp_path / "0001_b.sql").write_text("SELECT 1;")
    with pytest.raises(MigrationError, match="Duplicate"):
        discover_migrations(tmp_path)


# ---------------------------------------------------------------- integration


@pytest.mark.integration
def test_applies_all_migrations_once(fresh_database: str) -> None:
    first = migrate(fresh_database, DEFAULT_MIGRATIONS_DIR)
    second = migrate(fresh_database, DEFAULT_MIGRATIONS_DIR)
    assert len(first) == len(discover_migrations(DEFAULT_MIGRATIONS_DIR))
    assert second == []


@pytest.mark.integration
def test_creates_hypertable_policies_and_aggregates(migrated_database: str) -> None:
    with psycopg.connect(migrated_database) as conn:
        hypertables = conn.execute(
            "SELECT hypertable_schema || '.' || hypertable_name, compression_enabled "
            "FROM timescaledb_information.hypertables WHERE hypertable_schema = 'raw'"
        ).fetchall()
        assert hypertables == [("raw.station_status", True)]

        jobs = {
            (str(proc), str(table))
            for proc, table in conn.execute(
                "SELECT proc_name, hypertable_schema || '.' || hypertable_name "
                "FROM timescaledb_information.jobs WHERE hypertable_name IS NOT NULL"
            ).fetchall()
        }
        assert ("policy_compression", "raw.station_status") in jobs
        assert ("policy_retention", "raw.station_status") in jobs

        aggregates = {
            str(row[0])
            for row in conn.execute(
                "SELECT view_schema || '.' || view_name "
                "FROM timescaledb_information.continuous_aggregates"
            ).fetchall()
        }
        assert aggregates == {"agg.station_status_5min", "agg.station_status_hourly"}

        refresh_jobs = conn.execute(
            "SELECT count(*) FROM timescaledb_information.jobs "
            "WHERE proc_name = 'policy_refresh_continuous_aggregate'"
        ).fetchone()
        assert refresh_jobs == (2,)


@pytest.mark.integration
def test_refuses_edited_migration(fresh_database: str, tmp_path: Path) -> None:
    for path in DEFAULT_MIGRATIONS_DIR.glob("*.sql"):
        shutil.copy(path, tmp_path / path.name)
    migrate(fresh_database, tmp_path)
    edited = tmp_path / "0002_ops_ingestion_runs.sql"
    edited.write_text(edited.read_text() + "\n-- sneaky edit\n")
    with pytest.raises(MigrationError, match="changed after it was applied"):
        migrate(fresh_database, tmp_path)


@pytest.mark.integration
def test_failed_migration_is_not_recorded(fresh_database: str, tmp_path: Path) -> None:
    (tmp_path / "0001_ok.sql").write_text("CREATE TABLE public.ok_table (id int);")
    (tmp_path / "0002_broken.sql").write_text(
        "CREATE TABLE public.half_done (id int);\nSELECT * FROM no_such_table;"
    )
    with pytest.raises(MigrationError, match="0002_broken.sql failed"):
        migrate(fresh_database, tmp_path)
    with psycopg.connect(fresh_database) as conn:
        versions = conn.execute("SELECT version FROM ops.schema_migrations").fetchall()
        half_done = conn.execute("SELECT to_regclass('public.half_done')").fetchone()
    assert versions == [(1,)]
    assert half_done == (None,), "a transactional migration must roll back completely"


@pytest.mark.integration
def test_ensure_databases_is_idempotent(fresh_database: str) -> None:
    name = f"extra_{uuid.uuid4().hex[:8]}"
    assert ensure_databases(fresh_database, [name]) == [name]
    assert ensure_databases(fresh_database, [name]) == []
    with psycopg.connect(fresh_database, autocommit=True) as conn:
        assert conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        conn.execute(f'DROP DATABASE "{name}"')


def test_extra_databases_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKLINE_EXTRA_DATABASES", " dagster, ,other ")
    assert extra_databases_from_env() == ["dagster", "other"]
    monkeypatch.delenv("DOCKLINE_EXTRA_DATABASES")
    assert extra_databases_from_env() == []


@pytest.mark.integration
def test_reader_role_can_read_but_not_write(migrated_database: str) -> None:
    ensure_role_password(migrated_database, "dockline_reader", "reader-test-password")
    params = psycopg.conninfo.conninfo_to_dict(migrated_database)
    params["user"] = "dockline_reader"
    params["password"] = "reader-test-password"
    reader = psycopg.conninfo.make_conninfo(**{k: str(v) for k, v in params.items()})
    with psycopg.connect(reader, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM raw.station_status").fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM ops.ingestion_runs")


@pytest.mark.integration
def test_bi_role_sees_only_the_bi_schema(migrated_database: str) -> None:
    ensure_role_password(migrated_database, "dockline_bi", "bi-test-password")
    with psycopg.connect(migrated_database, autocommit=True) as conn:
        conn.execute("CREATE VIEW bi.probe AS SELECT 1 AS one")
    params = psycopg.conninfo.conninfo_to_dict(migrated_database)
    params["user"] = "dockline_bi"
    params["password"] = "bi-test-password"
    bi_user = psycopg.conninfo.make_conninfo(**{k: str(v) for k, v in params.items()})
    with psycopg.connect(bi_user, autocommit=True) as conn:
        assert conn.execute("SELECT one FROM bi.probe").fetchone() == (1,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT 1 FROM raw.station_status LIMIT 1")
