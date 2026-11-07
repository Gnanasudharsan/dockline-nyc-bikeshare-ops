{{
    config(
        materialized='incremental',
        unique_key=['station_id', 'hour_start'],
        incremental_strategy='delete+insert',
        on_schema_change='fail',
        indexes=[
            {'columns': ['station_id', 'hour_start'], 'unique': true},
            {'columns': ['hour_start']},
            {'columns': ['date_key']},
        ],
    )
}}

-- Grain: one row per station per clock hour. Built from fct_station_status_5min and kept
-- forever. Minutes columns are additive; averages are over in-service buckets only.

with buckets as (

    select *
    from {{ ref('fct_station_status_5min') }}
    {% if is_incremental() %}
        where bucket_start >= (
                select max(already_built.hour_start) - interval '{{ var("status_lookback_hours") }} hours'
                from {{ this }} as already_built
            )
    {% endif %}

)

select
    station_id,
    (array_agg(station_key order by bucket_start desc))[1] as station_key,
    date_trunc('hour', bucket_start) as hour_start,
    {{ date_key("date_trunc('hour', bucket_start)") }} as date_key,
    cast(extract(hour from {{ local_ts("date_trunc('hour', bucket_start)") }}) as integer)
        as hour_of_day,
    bool_or(is_peak_period) as is_peak_period,
    date_trunc('hour', bucket_start) as weather_hour,
    count(*) as bucket_count,
    count(*) * 5 as observed_minutes,
    sum(in_service_minutes) as in_service_minutes,
    sum(empty_minutes) as empty_minutes,
    sum(full_minutes) as full_minutes,
    sum(available_minutes) as available_minutes,
    sum(offline_minutes) as offline_minutes,
    round(avg(bikes_available) filter (where is_in_service), 2) as avg_bikes_available,
    round(avg(ebikes_available) filter (where is_in_service), 2) as avg_ebikes_available,
    round(avg(docks_available) filter (where is_in_service), 2) as avg_docks_available,
    round(avg(fill_ratio) filter (where is_in_service), 4) as avg_fill_ratio,
    min(min_bikes_available) as min_bikes_available,
    max(max_bikes_available) as max_bikes_available,
    (array_agg(bikes_available order by bucket_start desc))[1] as bikes_available_end,
    (array_agg(docks_available order by bucket_start desc))[1] as docks_available_end,
    (array_agg(imbalance_state order by bucket_start desc))[1] as imbalance_state_end,
    coalesce(sum(net_flow_bikes), 0) as net_flow_bikes,
    coalesce(sum(net_flow_bikes) filter (where net_flow_bikes > 0), 0) as bikes_added,
    coalesce(-sum(net_flow_bikes) filter (where net_flow_bikes < 0), 0) as bikes_removed,
    sum(report_count) as report_count
from buckets
group by station_id, date_trunc('hour', bucket_start)
