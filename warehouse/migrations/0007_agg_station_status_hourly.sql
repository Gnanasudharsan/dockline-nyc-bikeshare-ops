-- dockline:no-transaction
-- Hourly continuous aggregate built on the 5-minute aggregate (hierarchical).
-- Kept forever.
CREATE MATERIALIZED VIEW agg.station_status_hourly
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
SELECT
    time_bucket(INTERVAL '1 hour', bucket) AS bucket,
    station_id,
    last(bikes_available, bucket)   AS bikes_available,
    last(ebikes_available, bucket)  AS ebikes_available,
    last(docks_available, bucket)   AS docks_available,
    avg(bikes_available)            AS avg_bikes_available,
    avg(docks_available)            AS avg_docks_available,
    min(min_bikes_available)        AS min_bikes_available,
    max(max_bikes_available)        AS max_bikes_available,
    min(min_docks_available)        AS min_docks_available,
    max(max_docks_available)        AS max_docks_available,
    last(is_installed, bucket)      AS is_installed,
    last(is_renting, bucket)        AS is_renting,
    last(is_returning, bucket)      AS is_returning,
    sum(report_count)               AS report_count,
    count(*)                        AS buckets_with_reports,
    max(last_reported)              AS last_reported
FROM agg.station_status_5min
GROUP BY 1, station_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'agg.station_status_hourly',
    start_offset      => INTERVAL '3 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes'
);
