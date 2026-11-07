-- Station dimension, SCD Type 2. One row per station version; facts join on
-- station_id and their timestamp falling in [valid_from, valid_to).

with versions as (

    select
        *,
        row_number() over (partition by station_id order by dbt_valid_from) as version_number
    from {{ ref('snap_stations') }}

),

listing as (

    select
        station_id,
        last_seen_at
    from {{ ref('stg_gbfs__station_information') }}

)

select
    versions.dbt_scd_id as station_key,
    versions.station_id,
    versions.short_name,
    versions.station_name,
    versions.latitude,
    versions.longitude,
    versions.capacity,
    versions.region_id,
    versions.region_name,
    versions.has_ebike_charging,
    versions.nta_code,
    versions.neighborhood,
    versions.borough,
    versions.location_method,
    versions.version_number,
    -- The first version is valid from the beginning of time so facts recorded before the
    -- first snapshot still resolve to a station key.
    case
        when versions.version_number = 1 then cast('1900-01-01 00:00:00+00' as timestamptz)
        else versions.dbt_valid_from
    end as valid_from,
    versions.dbt_valid_to as valid_to,
    versions.dbt_valid_to = cast('9999-12-31 00:00:00+00' as timestamptz) as is_current,
    versions.first_seen_at,
    listing.last_seen_at,
    listing.last_seen_at > {{ as_of_timestamp() }} - interval '2 hours' as is_listed_in_feed
from versions
left join listing on versions.station_id = listing.station_id
