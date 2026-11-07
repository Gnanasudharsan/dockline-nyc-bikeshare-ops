-- Enable TimescaleDB and create the warehouse schemas.
--   raw: append-only data exactly as received (validated, typed).
--   agg: TimescaleDB continuous aggregates built from raw.
--   ops: operational metadata (ingestion audit log, migrations).
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS agg;
CREATE SCHEMA IF NOT EXISTS ops;

COMMENT ON SCHEMA raw IS 'Validated source data as received from GBFS and Open-Meteo.';
COMMENT ON SCHEMA agg IS 'TimescaleDB continuous aggregates over raw data.';
COMMENT ON SCHEMA ops IS 'Operational metadata: ingestion audit log and schema migrations.';
