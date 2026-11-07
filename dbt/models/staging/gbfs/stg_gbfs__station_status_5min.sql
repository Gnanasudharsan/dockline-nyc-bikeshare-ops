-- Last known state per station for each 5-minute bucket that had at least one report.
-- Buckets with no report are absent here; int_station_status_5min_filled fills them.

select
    station_id,
    bucket as bucket_start,
    bikes_available,
    ebikes_available,
    bikes_available - ebikes_available as classic_bikes_available,
    docks_available,
    bikes_disabled,
    docks_disabled,
    min_bikes_available,
    max_bikes_available,
    min_docks_available,
    max_docks_available,
    is_installed,
    is_renting,
    is_returning,
    report_count,
    last_reported as last_reported_at
from {{ source('gbfs_agg', 'station_status_5min') }}
