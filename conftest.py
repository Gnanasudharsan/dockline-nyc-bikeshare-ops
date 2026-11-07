"""Shared pytest fixtures: one throwaway TimescaleDB container per test session.

Integration tests (marked ``integration``) get a fresh database inside that container,
so they never touch the developer's local stack. Run unit tests only with
``pytest -m "not integration"``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

TIMESCALE_IMAGE = "timescale/timescaledb:2.31.0-pg16"
REPO_ROOT = Path(__file__).resolve().parent
MIGRATIONS_DIR = REPO_ROOT / "warehouse" / "migrations"


def _point_testcontainers_at_docker_desktop() -> None:
    """Docker Desktop on macOS uses a per-user socket that docker-py does not find alone."""
    if os.environ.get("DOCKER_HOST") or shutil.which("docker") is None:
        return
    result = subprocess.run(  # noqa: S603 - fixed arguments
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    host = result.stdout.strip()
    if result.returncode == 0 and host and host != "unix:///var/run/docker.sock":
        os.environ["DOCKER_HOST"] = host
        os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")


@pytest.fixture(scope="session")
def timescale_admin_conninfo() -> Iterator[str]:
    """Start TimescaleDB once and return a superuser connection string."""
    _point_testcontainers_at_docker_desktop()
    from testcontainers.community.postgres import PostgresContainer

    container = PostgresContainer(
        TIMESCALE_IMAGE, username="test", password="test", dbname="postgres", driver=None
    )
    container.start()
    try:
        url = container.get_connection_url()
        yield make_conninfo(url)
    finally:
        container.stop()


def _create_database(admin_conninfo: str) -> str:
    name = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    params = conninfo_to_dict(admin_conninfo)
    params["dbname"] = name
    return make_conninfo(**{key: str(value) for key, value in params.items()})


@pytest.fixture
def fresh_database(timescale_admin_conninfo: str) -> str:
    """An empty database (no migrations applied)."""
    return _create_database(timescale_admin_conninfo)


@pytest.fixture
def migrated_database(timescale_admin_conninfo: str) -> str:
    """A new database with every warehouse migration applied."""
    from dockline_warehouse.migrate import migrate

    conninfo = _create_database(timescale_admin_conninfo)
    migrate(conninfo, MIGRATIONS_DIR)
    return conninfo
