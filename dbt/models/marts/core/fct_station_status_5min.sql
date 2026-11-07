{{
    config(
        materialized='incremental',
        tags=['live'],
        unique_key=['station_id', 'bucket_start'],
        incremental_strategy='delete+insert',
        on_schema_change='fail',
        indexes=[
            {'columns': ['station_id', 'bucket_start'], 'unique': true},
            {'columns': ['bucket_start']},
            {'columns': ['date_key']},
        ],
        post_hook=["{{ prune_older_than('bucket_start', var('fact_5min_retention_days')) }}"],
    )
}}

-- Grain: one row per station per 5-minute bucket while the station is listed.
-- State is the station's last known state at the end of the bucket, so each row
-- stands for 5 station-minutes in that state (ADR 0010).

with filled as (

    select *
    from {{ ref('int_station_status_5min_filled') }}
    {% if is_incremental() %}
        where bucket_start >= (
                select max(already_built.bucket_start) - interval '{{ var("status_lookback_hours") }} hours'
                from {{ this }} as already_built
            )
    {% endif %}

),

classified as (

    select
        filled.*,
        filled.last_reported_at is null
        or filled.minutes_since_report > {{ var('stale_report_minutes') }} as is_stale
    from filled

),

flagged as (

    select
        *,
        not is_stale and coalesce(is_installed, false) and (is_renting or is_returning)
            as is_in_service
    from classified

),

measured as (

    select
        *,
        is_in_service and is_renting and bikes_available = 0 as is_empty,
        is_in_service and is_returning and docks_available = 0 as is_full,
        is_in_service
        and is_renting
        and is_returning
        and bikes_available >= 1
        and docks_available >= 1 as is_available,
        case
            when is_in_service
                then {{ safe_divide('bikes_available', 'bikes_available + docks_available') }}
        end as fill_ratio
    from flagged

)

select
    measured.station_id,
    station.station_key,
    measured.bucket_start,
    measured.bucket_end,
    {{ date_key('measured.bucket_start') }} as date_key,
    cast(extract(hour from {{ local_ts('measured.bucket_start') }}) as integer) * 100
    + cast(extract(minute from {{ local_ts('measured.bucket_start') }}) as integer) as time_key,
    date_trunc('hour', measured.bucket_start) as weather_hour,
    {{ is_peak_period('measured.bucket_start') }} as is_peak_period,
    measured.bikes_available,
    measured.ebikes_available,
    measured.classic_bikes_available,
    measured.docks_available,
    measured.bikes_disabled,
    measured.docks_disabled,
    measured.min_bikes_available,
    measured.max_bikes_available,
    measured.min_docks_available,
    measured.max_docks_available,
    measured.report_count,
    measured.has_report,
    measured.last_reported_at,
    measured.minutes_since_report,
    measured.is_installed,
    measured.is_renting,
    measured.is_returning,
    measured.is_stale,
    measured.is_in_service,
    measured.is_empty,
    measured.is_full,
    measured.is_available,
    round(measured.fill_ratio, 4) as fill_ratio,
    round(measured.fill_ratio - {{ var('target_fill_ratio') }}, 4) as imbalance_index,
    case
        when not measured.is_in_service then 'offline'
        when measured.bikes_available = 0
            or measured.fill_ratio <= {{ var('starving_fill_ratio') }} then 'starving'
        when measured.docks_available = 0
            or measured.fill_ratio >= {{ var('flooding_fill_ratio') }} then 'flooding'
        else 'balanced'
    end as imbalance_state,
    case
        when measured.is_in_service then
            cast(round(
                {{ var('target_fill_ratio') }}
                * (measured.bikes_available + measured.docks_available)
            ) as integer) - measured.bikes_available
    end as rebalance_need_bikes,
    measured.net_flow_bikes,
    case when measured.is_in_service then 5 else 0 end as in_service_minutes,
    case when measured.is_empty then 5 else 0 end as empty_minutes,
    case when measured.is_full then 5 else 0 end as full_minutes,
    case when measured.is_available then 5 else 0 end as available_minutes,
    case when not measured.is_in_service then 5 else 0 end as offline_minutes
from measured
left join {{ ref('dim_station') }} as station
    on
        measured.station_id = station.station_id
        and measured.bucket_start >= station.valid_from
        and measured.bucket_start < station.valid_to
