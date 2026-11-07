# 0007. A small in-house SQL migration runner

- Status: Accepted
- Date: 2026-11-07

## Context
The warehouse schema needs versioned, repeatable migrations. TimescaleDB continuous
aggregates cannot be created inside a transaction, which many tools assume. Options
considered: Alembic (Python-model-centric, awkward for hand-written TimescaleDB SQL),
dbmate/Flyway (separate binaries and images; fine, but one more moving part to run in
tests and CI), and a ~150-line runner.

## Decision
`dockline_warehouse.migrate` applies `NNNN_name.sql` files in order and records each in
`ops.schema_migrations` with a SHA-256 checksum. Files run in one transaction unless the
first line is `-- dockline:no-transaction`, in which case statements run one by one in
autocommit mode. A Postgres advisory lock serialises concurrent runs. It ships in the
ingestion image and runs as the one-shot `migrate` Compose service before ingestion starts.

## Consequences
- Plain SQL, easy to review; the same code path runs in tests, CI, and production.
- Editing an applied migration fails loudly, so schema history cannot drift.
- No down-migrations: fixes go forward as new files, which is the safer habit for a
  time-series warehouse anyway.
- If needs grow (branching, many contributors), swapping to dbmate is straightforward
  because the files are already plain SQL.
