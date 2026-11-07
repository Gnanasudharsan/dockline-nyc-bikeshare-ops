-- Every distinct station report from GBFS station_status.
-- A row is keyed by (station_id, last_reported): if a station has not reported
-- since the previous poll, the poll adds nothing for it (see ADR 0006).
CREATE TABLE raw.station_status (
    station_id            text        NOT NULL,
    last_reported         timestamptz NOT NULL,
    fetched_at            timestamptz NOT NULL,
    ingestion_run_id      bigint      NOT NULL,
    num_bikes_available   smallint    NOT NULL CHECK (num_bikes_available >= 0),
    num_ebikes_available  smallint    NOT NULL CHECK (num_ebikes_available >= 0),
    num_bikes_disabled    smallint    NOT NULL CHECK (num_bikes_disabled >= 0),
    num_docks_available   smallint    NOT NULL CHECK (num_docks_available >= 0),
    num_docks_disabled    smallint    NOT NULL CHECK (num_docks_disabled >= 0),
    is_installed          boolean     NOT NULL,
    is_renting            boolean     NOT NULL,
    is_returning          boolean     NOT NULL
);

SELECT create_hypertable(
    'raw.station_status',
    by_range('last_reported', INTERVAL '1 day')
);

-- Dedupe key. Includes the partitioning column, as hypertables require.
CREATE UNIQUE INDEX station_status_station_reported_uidx
    ON raw.station_status (station_id, last_reported DESC);

CREATE INDEX station_status_fetched_idx ON raw.station_status (fetched_at DESC);

-- Columnar compression after 7 days, grouped by station for fast per-station scans.
ALTER TABLE raw.station_status SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'station_id',
    timescaledb.compress_orderby = 'last_reported DESC'
);
SELECT add_compression_policy('raw.station_status', compress_after => INTERVAL '7 days');

-- Raw minute-level data is kept for 30 days; aggregates are kept forever.
SELECT add_retention_policy('raw.station_status', drop_after => INTERVAL '30 days');

COMMENT ON TABLE raw.station_status IS
    'Distinct GBFS station_status reports. Compressed after 7 days, dropped after 30.';
