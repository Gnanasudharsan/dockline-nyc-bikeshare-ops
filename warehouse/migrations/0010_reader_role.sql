-- Read-only role for the serving layer (Cube, Grafana). It can read every warehouse
-- schema but write nothing. The login password is not stored here: the migrate job
-- sets it from DOCKLINE_READER_PASSWORD on every run (see migrate.ensure_role_password).
--
-- dbt creates the model schemas on first run; creating them here (owned by the
-- migrating user, which is also the dbt user) lets the grants exist up front.
-- Tables dbt creates later are covered by dbt's `grants` config and by the default
-- privileges below.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dockline_reader') THEN
        CREATE ROLE dockline_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS snapshots;
CREATE SCHEMA IF NOT EXISTS reference;

GRANT USAGE ON SCHEMA raw, agg, ops, staging, intermediate, marts, snapshots, reference
    TO dockline_reader;

GRANT SELECT ON ALL TABLES IN SCHEMA raw, agg, ops, staging, intermediate, marts, snapshots, reference
    TO dockline_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA raw, agg, ops, staging, intermediate, marts, snapshots, reference
    GRANT SELECT ON TABLES TO dockline_reader;

-- Statements from BI tools should never run away with the warehouse.
ALTER ROLE dockline_reader SET statement_timeout = '60s';
