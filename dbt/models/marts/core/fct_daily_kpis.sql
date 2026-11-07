{{ config(tags=['daily']) }}

-- Grain: one row per local service date per borough. Every column is either additive
-- (minutes, bike movements) or a ratio recomputed from additive columns, so rows can be
-- summed across boroughs and the ratios recomputed.

with hourly as (

    select
        hourly.*,
        coalesce(station.borough, 'Unknown') as borough
    from {{ ref('fct_station_hourly') }} as hourly
    left join {{ ref('dim_station') }} as station
        on hourly.station_key = station.station_key

),

daily as (

    select
        date_key,
        borough,
        count(distinct station_id) filter (where in_service_minutes > 0) as stations_in_service,
        count(distinct station_id) as stations_listed,
        count(distinct hour_start) as hours_covered,
        sum(observed_minutes) as observed_station_minutes,
        sum(in_service_minutes) as in_service_station_minutes,
        sum(empty_minutes) as empty_station_minutes,
        sum(full_minutes) as full_station_minutes,
        sum(available_minutes) as available_station_minutes,
        sum(offline_minutes) as offline_station_minutes,
        sum(in_service_minutes) filter (where is_peak_period) as peak_in_service_station_minutes,
        sum(empty_minutes) filter (where is_peak_period) as peak_empty_station_minutes,
        sum(full_minutes) filter (where is_peak_period) as peak_full_station_minutes,
        sum(bikes_added) as bikes_added,
        sum(bikes_removed) as bikes_removed,
        sum(net_flow_bikes) as net_flow_bikes,
        -- Station-hours weighted average of bikes on hand, summed across stations.
        round(sum(avg_bikes_available) / nullif(count(distinct hour_start), 0), 1)
            as avg_bikes_available,
        round(sum(avg_ebikes_available) / nullif(count(distinct hour_start), 0), 1)
            as avg_ebikes_available,
        round(sum(avg_docks_available) / nullif(count(distinct hour_start), 0), 1)
            as avg_docks_available
    from hourly
    group by date_key, borough

),

weather as (

    select
        {{ date_key('weather_hour') }} as date_key,
        round(cast(avg(temperature_c) as numeric), 1) as avg_temperature_c,
        round(cast(max(temperature_c) as numeric), 1) as max_temperature_c,
        round(cast(sum(precipitation_mm) as numeric), 1) as total_precipitation_mm,
        mode() within group (order by weather_condition) as dominant_weather_condition
    from {{ ref('dim_weather') }}
    group by {{ date_key('weather_hour') }}

)

select
    daily.date_key || '-' || daily.borough as kpi_id,
    daily.date_key,
    dates.calendar_date as service_date,
    daily.borough,
    daily.stations_listed,
    daily.stations_in_service,
    daily.hours_covered,
    daily.observed_station_minutes,
    daily.in_service_station_minutes,
    daily.empty_station_minutes,
    daily.full_station_minutes,
    daily.available_station_minutes,
    daily.offline_station_minutes,
    round({{ safe_divide('daily.available_station_minutes', 'daily.in_service_station_minutes') }}, 4)
        as availability_rate,
    round({{ safe_divide('daily.empty_station_minutes', 'daily.in_service_station_minutes') }}, 4)
        as empty_rate,
    round({{ safe_divide('daily.full_station_minutes', 'daily.in_service_station_minutes') }}, 4)
        as full_rate,
    coalesce(daily.peak_in_service_station_minutes, 0) as peak_in_service_station_minutes,
    coalesce(daily.peak_empty_station_minutes, 0) as peak_empty_station_minutes,
    coalesce(daily.peak_full_station_minutes, 0) as peak_full_station_minutes,
    daily.bikes_added,
    daily.bikes_removed,
    daily.net_flow_bikes,
    daily.avg_bikes_available,
    daily.avg_ebikes_available,
    daily.avg_docks_available,
    weather.avg_temperature_c,
    weather.max_temperature_c,
    weather.total_precipitation_mm,
    weather.dominant_weather_condition,
    dates.calendar_date < cast({{ local_ts(as_of_timestamp()) }} as date) as is_complete_day
from daily
inner join {{ ref('dim_date') }} as dates on daily.date_key = dates.date_key
left join weather on daily.date_key = weather.date_key
