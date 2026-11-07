-- Phase 1 acceptance checks. Run with `make check-ingestion` after the stack has been
-- up for at least 15 minutes.
\pset footer off
\echo '== 1. Rows inserted per minute (last 15 minutes) — should be > 0 every minute'
SELECT date_trunc('minute', fetched_at) AS minute,
       count(*)                         AS rows_inserted,
       count(DISTINCT station_id)       AS stations_reporting
FROM raw.station_status
WHERE fetched_at > now() - INTERVAL '15 minutes'
GROUP BY 1
ORDER BY 1;

\echo '== 2. Duplicate (station_id, last_reported) pairs — must be 0'
SELECT count(*) AS duplicate_pairs
FROM (
    SELECT station_id, last_reported
    FROM raw.station_status
    GROUP BY 1, 2
    HAVING count(*) > 1
) AS d;

\echo '== 3. Ingestion run success rate (last 15 minutes) — must be 100%'
SELECT feed,
       count(*)                                              AS runs,
       count(*) FILTER (WHERE status = 'success')            AS succeeded,
       count(*) FILTER (WHERE status = 'failed')             AS failed,
       round(100.0 * count(*) FILTER (WHERE status = 'success') / count(*), 1) AS success_pct,
       round(avg(latency_ms))                                AS avg_latency_ms,
       sum(records_inserted)                                 AS inserted,
       sum(records_duplicate)                                AS duplicate,
       sum(records_rejected)                                 AS rejected
FROM ops.ingestion_runs
WHERE started_at > now() - INTERVAL '15 minutes'
GROUP BY feed
ORDER BY feed;

\echo '== 4. Data freshness — seconds since the newest report'
SELECT round(extract(epoch FROM now() - max(last_reported))) AS data_freshness_seconds,
       max(fetched_at)                                       AS last_fetch
FROM raw.station_status;

\echo '== 5. System-wide availability from the 5-minute aggregate, last 2 hours (timed — target < 500 ms)'
\timing on
SELECT bucket,
       count(*)                                        AS stations,
       sum(bikes_available)                            AS bikes_available,
       sum(docks_available)                            AS docks_available,
       count(*) FILTER (WHERE bikes_available = 0 AND is_renting)   AS empty_stations,
       count(*) FILTER (WHERE docks_available = 0 AND is_returning) AS full_stations
FROM agg.station_status_5min
WHERE bucket > now() - INTERVAL '2 hours'
GROUP BY bucket
ORDER BY bucket DESC
LIMIT 24;
\timing off

\echo '== 6. Storage'
SELECT hypertable_name,
       pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) AS size
FROM timescaledb_information.hypertables;
