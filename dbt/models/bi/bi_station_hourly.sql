{{ config(alias='station_hourly') }}

-- Hourly station activity. Column names avoid the Power BI measure names
-- (empty_station_minutes, bikes_added, ...), which are defined in DAX.

select
    station_key,
    date_key,
    hour_of_day,
    cast(extract(epoch from weather_hour) / 3600 as bigint) as weather_hour_key,
    {{ local_ts('hour_start') }} as hour_start_local,
    is_peak_period,
    observed_minutes,
    in_service_minutes,
    empty_minutes,
    full_minutes,
    available_minutes,
    offline_minutes,
    avg_bikes_available as avg_station_bikes,
    avg_docks_available as avg_station_docks,
    avg_fill_ratio as avg_station_fill_ratio,
    net_flow_bikes,
    bikes_added as added_bikes,
    bikes_removed as removed_bikes,
    imbalance_state_end
from {{ ref('fct_station_hourly') }}
