"""Apply versioned SQL migrations to the Dockline warehouse.

Design (see ADR 0007):
- Migrations are files named ``NNNN_description.sql`` in one directory, applied in
  version order exactly once.
- Each applied migration is recorded in ``ops.schema_migrations`` with a SHA-256
  checksum. Editing an applied file is an error: write a new migration instead.
- A file whose first line is ``-- dockline:no-transaction`` runs statement by statement
  in autocommit mode. TimescaleDB needs this for ``CREATE MATERIALIZED VIEW ... WITH
  (timescaledb.continuous)``. Every other file runs inside a single transaction.
- A Postgres advisory lock stops two migrators from running at the same time.

Usage: ``python -m dockline_warehouse.migrate`` (reads POSTGRES_* environment variables).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
import sqlparse
from psycopg import sql

logger = logging.getLogger("dockline.migrate")

NO_TRANSACTION_MARKER = "-- dockline:no-transaction"
MIGRATION_FILENAME = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")
# Arbitrary constant shared by every migrator process.
ADVISORY_LOCK_KEY = 4_204_202_026

DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


class MigrationError(RuntimeError):
    """Raised when migrations are inconsistent or fail to apply."""


@dataclass(frozen=True)
class Migration:
    """One migration file on disk."""

    version: int
    name: str
    path: Path
    sql_text: str

    @property
    def checksum(self) -> str:
        """SHA-256 of the file contents, used to detect edits after apply."""
        return hashlib.sha256(self.sql_text.encode("utf-8")).hexdigest()

    @property
    def runs_in_transaction(self) -> bool:
        """Whether the file must run inside a single transaction."""
        first_line = self.sql_text.lstrip().splitlines()[0] if self.sql_text.strip() else ""
        return first_line.strip() != NO_TRANSACTION_MARKER


def discover_migrations(directory: Path) -> list[Migration]:
    """Return the migrations in ``directory`` sorted by version.

    Raises MigrationError for badly named files or duplicate versions.
    """
    migrations: list[Migration] = []
    seen_versions: set[int] = set()
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_FILENAME.match(path.name)
        if match is None:
            raise MigrationError(f"Migration file name must look like 0001_name.sql: {path.name}")
        version = int(match["version"])
        if version in seen_versions:
            raise MigrationError(f"Duplicate migration version {version:04d}")
        seen_versions.add(version)
        migrations.append(
            Migration(version=version, name=match["name"], path=path, sql_text=path.read_text())
        )
    return sorted(migrations, key=lambda migration: migration.version)


def _ensure_tracking_table(conn: psycopg.Connection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS ops")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.schema_migrations (
            version     integer     PRIMARY KEY,
            name        text        NOT NULL,
            checksum    text        NOT NULL,
            applied_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def _applied_checksums(conn: psycopg.Connection) -> dict[int, str]:
    rows = conn.execute("SELECT version, checksum FROM ops.schema_migrations").fetchall()
    return {int(version): str(checksum) for version, checksum in rows}


def _record(conn: psycopg.Connection, migration: Migration) -> None:
    conn.execute(
        "INSERT INTO ops.schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
        (migration.version, migration.name, migration.checksum),
    )


def _apply(conn: psycopg.Connection, migration: Migration) -> None:
    if migration.runs_in_transaction:
        with conn.transaction():
            conn.execute(sql.SQL(migration.sql_text))
            _record(conn, migration)
        return
    # Autocommit mode: run each statement on its own so TimescaleDB can create
    # continuous aggregates. A failure part-way leaves earlier statements applied,
    # so these files should be small and use IF NOT EXISTS where possible.
    for statement in sqlparse.split(migration.sql_text):
        if sqlparse.format(statement, strip_comments=True).strip():
            conn.execute(sql.SQL(statement))
    _record(conn, migration)


def migrate(conninfo: str, directory: Path = DEFAULT_MIGRATIONS_DIR) -> list[Migration]:
    """Apply every pending migration in ``directory`` and return the ones applied.

    Raises MigrationError if an applied migration's file has changed or disappeared.
    """
    migrations = discover_migrations(directory)
    applied_now: list[Migration] = []
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        try:
            _ensure_tracking_table(conn)
            applied = _applied_checksums(conn)
            on_disk = {migration.version for migration in migrations}
            missing = sorted(set(applied) - on_disk)
            if missing:
                raise MigrationError(f"Applied migrations missing from disk: {missing}")
            for migration in migrations:
                if migration.version in applied:
                    if applied[migration.version] != migration.checksum:
                        raise MigrationError(
                            f"Migration {migration.path.name} changed after it was applied. "
                            "Write a new migration instead of editing an old one."
                        )
                    continue
                logger.info("applying migration %s", migration.path.name)
                try:
                    _apply(conn, migration)
                except psycopg.Error as error:
                    raise MigrationError(f"{migration.path.name} failed: {error}") from error
                applied_now.append(migration)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
    return applied_now


def conninfo_from_env() -> str:
    """Build a libpq connection string from POSTGRES_* environment variables."""
    return psycopg.conninfo.make_conninfo(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5433"),
        user=os.environ.get("POSTGRES_USER", "dockline"),
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ.get("POSTGRES_DB", "dockline"),
        application_name="dockline-migrate",
    )


def ensure_databases(conninfo: str, names: list[str]) -> list[str]:
    """Create each named database on the same server if it does not exist yet.

    Used for service metadata stores that live beside the warehouse (for example
    Dagster's run storage). Returns the names that were created.
    """
    created: list[str] = []
    with psycopg.connect(conninfo, autocommit=True) as conn:
        for name in names:
            exists = conn.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (name,)
            ).fetchone()
            if exists:
                continue
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            logger.info("created database %s", name)
            created.append(name)
    return created


def ensure_role_password(conninfo: str, role: str, password: str) -> None:
    """Set the login password of an existing role (idempotent).

    Passwords never live in migration files; they come from the environment and are
    re-applied on every migrate run, so rotating one is: change .env, rerun migrate.
    """
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(
            sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
    logger.info("password set for role %s", role)


def extra_databases_from_env() -> list[str]:
    """Parse DOCKLINE_EXTRA_DATABASES (comma separated) into a list of names."""
    raw = os.environ.get("DOCKLINE_EXTRA_DATABASES", "")
    return [name.strip() for name in raw.split(",") if name.strip()]


def main() -> int:
    """Command-line entry point. Returns a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    directory = Path(os.environ.get("MIGRATIONS_DIR", str(DEFAULT_MIGRATIONS_DIR)))
    conninfo = conninfo_from_env()
    try:
        applied = migrate(conninfo, directory)
        ensure_databases(conninfo, extra_databases_from_env())
        reader_password = os.environ.get("DOCKLINE_READER_PASSWORD", "")
        if reader_password:
            ensure_role_password(conninfo, "dockline_reader", reader_password)
    except (MigrationError, psycopg.Error) as error:
        logger.error("%s", error)
        return 1
    logger.info("migrations complete: %d applied", len(applied))
    return 0


if __name__ == "__main__":
    sys.exit(main())
