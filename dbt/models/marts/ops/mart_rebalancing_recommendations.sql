{{ config(materialized='view') }}

-- Live rebalancing board: one row per current station, computed at query time from the
-- real-time 5-minute aggregate (so it is never older than the latest feed poll).
--
-- rebalance_need_bikes = bikes to add (positive) or remove (negative) to reach the
-- target fill ratio. Only starving or flooding stations get a recommendation; they are
-- ranked by bikes to move, weighted by how busy the station usually is at this hour.

with latest as (

    select distinct on (station_id) *
    from {{ ref('stg_gbfs__station_status_5min') }}
    where bucket_start >= {{ as_of_timestamp() }} - interval '6 hours'
    order by station_id asc, bucket_start desc

),

stations as (

    select *
    from {{ ref('dim_station') }}
    where is_current and is_listed_in_feed

),

typical_turnover as (

    -- Average bikes moved (in + out) at this station in the same local hour of day over
    -- the chronic lookback window.
    select
        station_id,
        avg(bikes_added + bikes_removed) as typical_hourly_turnover
    from {{ ref('fct_station_hourly') }}
    where
        hour_start >= {{ as_of_timestamp() }} - interval '{{ var("chronic_lookback_days") }} days'
        and hour_of_day = cast(extract(hour from {{ local_ts(as_of_timestamp()) }}) as integer)
    group by station_id

),

current_state as (

    select
        stations.station_id,
        stations.station_key,
        stations.station_name,
        stations.borough,
        stations.neighborhood,
        stations.latitude,
        stations.longitude,
        stations.capacity,
        latest.bikes_available,
        latest.ebikes_available,
        latest.docks_available,
        latest.bikes_disabled,
        latest.docks_disabled,
        latest.last_reported_at,
        round(
            extract(epoch from ({{ as_of_timestamp() }} - latest.last_reported_at)) / 60.0, 1
        ) as minutes_since_report,
        coalesce(
            latest.last_reported_at
            > {{ as_of_timestamp() }} - interval '{{ var("stale_report_minutes") }} minutes'
            and latest.is_installed
            and (latest.is_renting or latest.is_returning),
            false
        ) as is_in_service,
        coalesce(turnover.typical_hourly_turnover, 0) as typical_hourly_turnover
    from stations
    left join latest on stations.station_id = latest.station_id
    left join typical_turnover as turnover on stations.station_id = turnover.station_id

),

scored as (

    select
        *,
        case
            when is_in_service
                then round({{ safe_divide('bikes_available', 'bikes_available + docks_available') }}, 4)
        end as fill_ratio,
        case
            when is_in_service then
                cast(round(
                    {{ var('target_fill_ratio') }} * (bikes_available + docks_available)
                ) as integer) - bikes_available
        end as rebalance_need_bikes
    from current_state

),

classified as (

    select
        *,
        round(fill_ratio - {{ var('target_fill_ratio') }}, 4) as imbalance_index,
        case
            when not is_in_service then 'offline'
            when bikes_available = 0 or fill_ratio <= {{ var('starving_fill_ratio') }}
                then 'starving'
            when docks_available = 0 or fill_ratio >= {{ var('flooding_fill_ratio') }}
                then 'flooding'
            else 'balanced'
        end as imbalance_state
    from scored

),

recommended as (

    select
        *,
        case
            when imbalance_state = 'starving' and rebalance_need_bikes > 0 then 'Add bikes'
            when imbalance_state = 'flooding' and rebalance_need_bikes < 0 then 'Remove bikes'
            else 'No action'
        end as recommended_action,
        case
            when imbalance_state in ('starving', 'flooding') then abs(rebalance_need_bikes)
            else 0
        end as bikes_to_move
    from classified

)

select
    *,
    round(cast(bikes_to_move * (1 + ln(1 + typical_hourly_turnover)) as numeric), 2)
        as priority_score,
    case
        when bikes_to_move > 0 then
            rank() over (
                partition by bikes_to_move > 0
                order by bikes_to_move * (1 + ln(1 + typical_hourly_turnover)) desc, station_id
            )
    end as priority_rank,
    {{ as_of_timestamp() }} as computed_at
from recommended
