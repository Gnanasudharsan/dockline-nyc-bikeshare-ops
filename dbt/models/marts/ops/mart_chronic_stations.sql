{{ config(tags=['daily']) }}

-- Stations that are chronically empty or full during weekday peaks.
-- A station is chronic when, over the trailing lookback window, more than the threshold
-- share of its in-service peak minutes were empty (or full). Stations with too few
-- observed peak hours are labelled insufficient_data rather than given a verdict.

with peak_hours as (

    select
        station_id,
        count(*) filter (where in_service_minutes > 0) as peak_hours_observed,
        sum(in_service_minutes) as peak_in_service_minutes,
        sum(empty_minutes) as peak_empty_minutes,
        sum(full_minutes) as peak_full_minutes
    from {{ ref('fct_station_hourly') }}
    where
        is_peak_period
        and hour_start >= {{ as_of_timestamp() }} - interval '{{ var("chronic_lookback_days") }} days'
    group by station_id

),

stations as (

    select * from {{ ref('dim_station') }}
    where is_current

),

rated as (

    select
        stations.station_id,
        stations.station_key,
        stations.station_name,
        stations.borough,
        stations.neighborhood,
        stations.capacity,
        coalesce(peak_hours.peak_hours_observed, 0) as peak_hours_observed,
        coalesce(peak_hours.peak_in_service_minutes, 0) as peak_in_service_minutes,
        coalesce(peak_hours.peak_empty_minutes, 0) as peak_empty_minutes,
        coalesce(peak_hours.peak_full_minutes, 0) as peak_full_minutes,
        round({{ safe_divide('peak_hours.peak_empty_minutes', 'peak_hours.peak_in_service_minutes') }}, 4)
            as peak_empty_share,
        round({{ safe_divide('peak_hours.peak_full_minutes', 'peak_hours.peak_in_service_minutes') }}, 4)
            as peak_full_share
    from stations
    left join peak_hours on stations.station_id = peak_hours.station_id

)

select
    *,
    case
        when peak_hours_observed < {{ var('chronic_min_peak_hours') }} then 'insufficient_data'
        when peak_empty_share > {{ var('chronic_share_threshold') }}
            and peak_full_share > {{ var('chronic_share_threshold') }} then 'chronic_empty_and_full'
        when peak_empty_share > {{ var('chronic_share_threshold') }} then 'chronic_empty'
        when peak_full_share > {{ var('chronic_share_threshold') }} then 'chronic_full'
        else 'ok'
    end as chronic_status,
    peak_hours_observed >= {{ var('chronic_min_peak_hours') }}
    and (
        peak_empty_share > {{ var('chronic_share_threshold') }}
        or peak_full_share > {{ var('chronic_share_threshold') }}
    ) as chronic_problem_station,
    {{ var('chronic_lookback_days') }} as lookback_days,
    {{ as_of_timestamp() }} as computed_at
from rated
