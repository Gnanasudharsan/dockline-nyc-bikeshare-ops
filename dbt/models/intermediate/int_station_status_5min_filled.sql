{{
    config(
        materialized='incremental',
        unique_key=['station_id', 'bucket_start'],
        incremental_strategy='delete+insert',
        on_schema_change='fail',
        indexes=[
            {'columns': ['station_id', 'bucket_start'], 'unique': true},
            {'columns': ['bucket_start']},
        ],
        post_hook=["{{ prune_older_than('bucket_start', var('fact_5min_retention_days')) }}"],
    )
}}

-- A complete station x 5-minute grid with each station's last known state carried
-- forward (last observation carried forward, ADR 0006).
--
-- raw.station_status only stores a row when a station reports something new, and the
-- 5-minute aggregate only has buckets with reports. Time-weighted metrics such as
-- "minutes empty" need the state for every bucket, so this model:
--   1. builds the grid of (station, bucket) pairs for the processing window;
--   2. seeds each station with its state just before the window;
--   3. fills each bucket with the most recent report at or before it.
--
-- Incremental runs rebuild the last `status_lookback_hours` to absorb late reports.

{%- set retention_days = var('fact_5min_retention_days') %}

{%- set first_possible_bucket %}
    greatest(
        (
            select {{ bucket_5min('min(started_at)') }}
            from {{ ref('stg_ops__ingestion_runs') }}
            where feed = 'station_status'
        ),
        {{ bucket_5min(as_of_timestamp()) }} - interval '{{ retention_days }} days'
    )
{%- endset %}

with bounds as (

    select
        {% if is_incremental() -%}
            coalesce(
                (select max(bucket_start) from {{ this }})
                - interval '{{ var("status_lookback_hours") }} hours',
                {{ first_possible_bucket }}
            ) as window_start,
        {%- else -%}
            {{ first_possible_bucket }} as window_start,
        {%- endif %}
        -- The last bucket that has fully ended.
        {{ bucket_5min(as_of_timestamp()) }} - interval '5 minutes' as window_end

),

buckets as (

    select
        generate_series(bounds.window_start, bounds.window_end, interval '5 minutes')
            as bucket_start
    from bounds

),

stations as (

    select
        station_id,
        first_seen_at,
        last_seen_at
    from {{ ref('stg_gbfs__station_information') }}

),

grid as (

    -- Only while the station is listed in the feed (station_information is polled
    -- hourly, so allow two hours after it was last seen).
    select
        stations.station_id,
        buckets.bucket_start
    from stations
    cross join buckets
    where
        buckets.bucket_start + interval '5 minutes' > stations.first_seen_at
        and buckets.bucket_start < stations.last_seen_at + interval '2 hours'

),

observed as (

    select status.*
    from {{ ref('stg_gbfs__station_status_5min') }} as status
    cross join bounds
    where status.bucket_start between bounds.window_start and bounds.window_end

),

seed as (

    -- Each station's state in the bucket just before the window.
    {% if is_incremental() -%}
        select
            previous.station_id,
            previous.bikes_available,
            previous.ebikes_available,
            previous.classic_bikes_available,
            previous.docks_available,
            previous.bikes_disabled,
            previous.docks_disabled,
            previous.is_installed,
            previous.is_renting,
            previous.is_returning,
            previous.last_reported_at
        from {{ this }} as previous
        cross join bounds
        where previous.bucket_start = bounds.window_start - interval '5 minutes'
    {%- else -%}
        select
            stations.station_id,
            prior_state.bikes_available,
            prior_state.ebikes_available,
            prior_state.classic_bikes_available,
            prior_state.docks_available,
            prior_state.bikes_disabled,
            prior_state.docks_disabled,
            prior_state.is_installed,
            prior_state.is_renting,
            prior_state.is_returning,
            prior_state.last_reported_at
        from stations
        cross join bounds
        cross join lateral (
            select status.*
            from {{ ref('stg_gbfs__station_status_5min') }} as status
            where
                status.station_id = stations.station_id
                and status.bucket_start < bounds.window_start
                and status.bucket_start >= bounds.window_start - interval '{{ retention_days }} days'
            order by status.bucket_start desc
            limit 1
        ) as prior_state
    {%- endif %}

),

timeline as (

    select
        grid.station_id,
        grid.bucket_start,
        false as is_seed,
        observed.bikes_available,
        observed.ebikes_available,
        observed.classic_bikes_available,
        observed.docks_available,
        observed.bikes_disabled,
        observed.docks_disabled,
        observed.is_installed,
        observed.is_renting,
        observed.is_returning,
        observed.last_reported_at,
        observed.min_bikes_available,
        observed.max_bikes_available,
        observed.min_docks_available,
        observed.max_docks_available,
        coalesce(observed.report_count, 0) as report_count
    from grid
    left join observed
        on
            grid.station_id = observed.station_id
            and grid.bucket_start = observed.bucket_start

    union all

    select
        seed.station_id,
        bounds.window_start - interval '5 minutes' as bucket_start,
        true as is_seed,
        seed.bikes_available,
        seed.ebikes_available,
        seed.classic_bikes_available,
        seed.docks_available,
        seed.bikes_disabled,
        seed.docks_disabled,
        seed.is_installed,
        seed.is_renting,
        seed.is_returning,
        seed.last_reported_at,
        null as min_bikes_available,
        null as max_bikes_available,
        null as min_docks_available,
        null as max_docks_available,
        0 as report_count
    from seed
    cross join bounds

),

state_groups as (

    -- Every reported bucket starts a new group; quiet buckets join the group of the
    -- latest report before them.
    select
        *,
        count(last_reported_at) over (
            partition by station_id
            order by bucket_start
            rows between unbounded preceding and current row
        ) as state_group
    from timeline

),

filled as (

    select
        station_id,
        bucket_start,
        is_seed,
        report_count,
        first_value(bikes_available) over state_window as bikes_available,
        first_value(ebikes_available) over state_window as ebikes_available,
        first_value(classic_bikes_available) over state_window as classic_bikes_available,
        first_value(docks_available) over state_window as docks_available,
        first_value(bikes_disabled) over state_window as bikes_disabled,
        first_value(docks_disabled) over state_window as docks_disabled,
        first_value(is_installed) over state_window as is_installed,
        first_value(is_renting) over state_window as is_renting,
        first_value(is_returning) over state_window as is_returning,
        first_value(last_reported_at) over state_window as last_reported_at,
        min_bikes_available,
        max_bikes_available,
        min_docks_available,
        max_docks_available
    from state_groups
    window state_window as (partition by station_id, state_group order by bucket_start)

),

with_flow as (

    select
        *,
        bikes_available - lag(bikes_available) over (
            partition by station_id order by bucket_start
        ) as net_flow_bikes
    from filled

)

select
    station_id,
    bucket_start,
    bucket_start + interval '5 minutes' as bucket_end,
    bikes_available,
    ebikes_available,
    classic_bikes_available,
    docks_available,
    bikes_disabled,
    docks_disabled,
    is_installed,
    is_renting,
    is_returning,
    last_reported_at,
    report_count,
    report_count > 0 as has_report,
    coalesce(min_bikes_available, bikes_available) as min_bikes_available,
    coalesce(max_bikes_available, bikes_available) as max_bikes_available,
    coalesce(min_docks_available, docks_available) as min_docks_available,
    coalesce(max_docks_available, docks_available) as max_docks_available,
    net_flow_bikes,
    round(
        extract(epoch from (bucket_start + interval '5 minutes' - last_reported_at)) / 60.0, 1
    ) as minutes_since_report
from with_flow
where not is_seed
