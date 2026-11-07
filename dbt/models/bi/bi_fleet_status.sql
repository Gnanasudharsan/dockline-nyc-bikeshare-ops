{{ config(alias='fleet_status') }}

-- Live state of every listed station (a view over the live rebalancing mart, so each
-- DirectQuery refresh sees the latest feed poll). Per-station values are prefixed
-- station_ so they do not collide with the DAX measures that aggregate them.

select
    station_key,
    bikes_available as station_bikes_available,
    ebikes_available as station_ebikes_available,
    docks_available as station_docks_available,
    bikes_disabled as station_bikes_disabled,
    docks_disabled as station_docks_disabled,
    is_in_service,
    fill_ratio as station_fill_ratio,
    imbalance_index as station_imbalance_index,
    imbalance_state,
    rebalance_need_bikes as station_rebalance_need_bikes,
    recommended_action,
    bikes_to_move,
    priority_score,
    priority_rank,
    typical_hourly_turnover,
    minutes_empty,
    is_high_traffic,
    minutes_since_report,
    last_reported_at at time zone 'UTC' as last_reported_at_utc,
    {{ local_ts('last_reported_at') }} as last_reported_at_local,
    computed_at at time zone 'UTC' as computed_at_utc
from {{ ref('mart_rebalancing_recommendations') }}
