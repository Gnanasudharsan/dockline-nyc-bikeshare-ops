-- Phase 2 acceptance checks: dbt marts and Dagster runs.
-- Run with `make check-pipeline` (pipes this file into psql in the timescaledb container).

\echo '== 1. Mart row counts'
SELECT 'dim_station' AS model, count(*) AS row_count FROM marts.dim_station
UNION ALL SELECT 'dim_date', count(*) FROM marts.dim_date
UNION ALL SELECT 'dim_time', count(*) FROM marts.dim_time
UNION ALL SELECT 'dim_weather', count(*) FROM marts.dim_weather
UNION ALL SELECT 'fct_station_status_5min', count(*) FROM marts.fct_station_status_5min
UNION ALL SELECT 'fct_station_hourly', count(*) FROM marts.fct_station_hourly
UNION ALL SELECT 'fct_daily_kpis', count(*) FROM marts.fct_daily_kpis
UNION ALL SELECT 'mart_rebalancing_recommendations', count(*) FROM marts.mart_rebalancing_recommendations
UNION ALL SELECT 'mart_chronic_stations', count(*) FROM marts.mart_chronic_stations
UNION ALL SELECT 'snap_stations', count(*) FROM snapshots.snap_stations
UNION ALL SELECT 'snap_daily_kpis', count(*) FROM snapshots.snap_daily_kpis;

\echo '== 2. Grid completeness, last 2 hours of 5-minute facts (expected = actual)'
WITH buckets AS (
    SELECT DISTINCT bucket_start
    FROM marts.fct_station_status_5min
    WHERE bucket_start > now() - interval '2 hours'
)
SELECT
    (SELECT count(*) FROM buckets) AS buckets,
    count(*) AS actual_rows,
    count(DISTINCT station_id) * (SELECT count(*) FROM buckets) AS expected_rows,
    count(*) FILTER (WHERE station_key IS NULL) AS rows_without_station_key
FROM marts.fct_station_status_5min
WHERE bucket_start > now() - interval '2 hours';

\echo '== 3. Mart freshness (minutes since the newest fact bucket ended)'
SELECT
    round(extract(epoch FROM now() - max(bucket_end)) / 60.0, 1) AS minutes_behind_5min,
    (SELECT max(hour_start) FROM marts.fct_station_hourly) AS newest_hour
FROM marts.fct_station_status_5min;

\echo '== 4. Station placement by borough'
SELECT borough, location_method, count(*) AS stations
FROM marts.dim_station
WHERE is_current
GROUP BY borough, location_method
ORDER BY borough, location_method;

\echo '== 5. Daily KPIs (most recent day)'
SELECT service_date, borough, stations_in_service, hours_covered, availability_rate,
       empty_rate, full_rate, bikes_added, bikes_removed, is_complete_day
FROM marts.fct_daily_kpis
WHERE service_date = (SELECT max(service_date) FROM marts.fct_daily_kpis)
ORDER BY borough;

\echo '== 6. Rebalancing board: network summary and top 10'
SELECT imbalance_state, count(*) AS stations, sum(bikes_to_move) AS bikes_to_move
FROM marts.mart_rebalancing_recommendations
GROUP BY imbalance_state
ORDER BY imbalance_state;

SELECT priority_rank, station_name, borough, bikes_available, docks_available,
       recommended_action, bikes_to_move, priority_score
FROM marts.mart_rebalancing_recommendations
WHERE priority_rank <= 10
ORDER BY priority_rank;

\echo '== 7. Alerts recorded in the last 24 hours'
SELECT occurred_at, event_type, severity, title
FROM ops.pipeline_events
WHERE occurred_at > now() - interval '24 hours'
ORDER BY occurred_at DESC
LIMIT 20;

\echo '== 8. Dagster runs in the last 24 hours, by job and status'
\c dagster
SELECT pipeline_name AS job, status, count(*) AS runs, max(create_timestamp) AS latest
FROM runs
WHERE create_timestamp > now() - interval '24 hours'
GROUP BY pipeline_name, status
ORDER BY pipeline_name, status;
