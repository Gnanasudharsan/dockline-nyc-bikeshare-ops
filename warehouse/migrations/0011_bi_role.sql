-- Read-only login for Power BI Desktop (DirectQuery from the Windows VM).
-- It sees only the `bi` schema: dbt views shaped for Power BI (models/bi). The views
-- run with their owner's rights, so dockline_bi needs no access to marts or raw data.
-- Its password is set by the migrate job from DOCKLINE_BI_PASSWORD.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dockline_bi') THEN
        CREATE ROLE dockline_bi LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS bi;

GRANT USAGE ON SCHEMA bi TO dockline_bi, dockline_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA bi TO dockline_bi, dockline_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA bi GRANT SELECT ON TABLES TO dockline_bi, dockline_reader;

-- DirectQuery issues one SQL statement per visual; none should run longer than this.
ALTER ROLE dockline_bi SET statement_timeout = '120s';
