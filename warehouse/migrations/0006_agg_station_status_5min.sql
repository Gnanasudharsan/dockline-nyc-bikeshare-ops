-- dockline:no-transaction
-- 5-minute continuous aggregate per station. Kept forever (no retention policy).
-- Real-time aggregation (materialized_only = false) merges not-yet-materialized raw
-- rows at query time, so live dashboards see the latest minute.
CREATE MATERIALIZED VIEW agg.station_status_5min
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket(INTERVAL '5 minutes', last_reported) AS bucket,
    station_id,
    last(num_bikes_available, last_reported)  AS bikes_available,
    last(num_ebikes_available, last_reported) AS ebikes_available,
    last(num_docks_available, last_reported)  AS docks_available,
    last(num_bikes_disabled, last_reported)   AS bikes_disabled,
    last(num_docks_disabled, last_reported)   AS docks_disabled,
    min(num_bikes_available)                  AS min_bikes_available,
    max(num_bikes_available)                  AS max_bikes_available,
    min(num_docks_available)                  AS min_docks_available,
    max(num_docks_available)                  AS max_docks_available,
    last(is_installed, last_reported)         AS is_installed,
    last(is_renting, last_reported)           AS is_renting,
    last(is_returning, last_reported)         AS is_returning,
    count(*)                                  AS report_count,
    max(last_reported)                        AS last_reported
FROM raw.station_status
GROUP BY bucket, station_id
WITH NO DATA;

-- Refresh only the last 3 days. This must stay well inside the 30-day raw
-- retention window, otherwise refreshing would erase history that raw no longer has.
SELECT add_continuous_aggregate_policy(
    'agg.station_status_5min',
    start_offset      => INTERVAL '3 days',
    end_offset        => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes'
);
