"""Dagster resources: a small warehouse client for checks and alerts."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

import dagster as dg
import psycopg
from psycopg.conninfo import make_conninfo


class WarehouseResource(dg.ConfigurableResource):  # type: ignore[type-arg]
    """Connection details for the Dockline warehouse (read from POSTGRES_* env vars)."""

    host: str = os.environ.get("POSTGRES_HOST", "localhost")
    port: int = int(os.environ.get("POSTGRES_PORT", "5433"))
    user: str = os.environ.get("POSTGRES_USER", "dockline")
    password: str = dg.EnvVar("POSTGRES_PASSWORD")
    dbname: str = os.environ.get("POSTGRES_DB", "dockline")

    def conninfo(self) -> str:
        """Return a libpq connection string."""
        return make_conninfo(
            host=self.host,
            port=str(self.port),
            user=self.user,
            password=self.password,
            dbname=self.dbname,
            application_name="dockline-orchestration",
        )

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection[tuple[object, ...]]]:
        """Open an autocommit connection for the duration of a ``with`` block."""
        with psycopg.connect(self.conninfo(), autocommit=True, connect_timeout=10) as conn:
            yield conn
