{% snapshot snap_stations %}

{{
    config(
        unique_key='station_id',
        strategy='timestamp',
        updated_at='attributes_updated_at',
        dbt_valid_to_current="cast('9999-12-31 00:00:00+00' as timestamptz)",
        tags=['hourly'],
    )
}}

-- SCD Type 2 history of station attributes. The ingestion service only bumps
-- attributes_updated_at when a tracked attribute really changes, so each change in
-- name, location, capacity, or region opens a new version stamped with the time the
-- change was observed. last_seen_at is deliberately excluded: it moves every hour.

select
    station_id,
    short_name,
    station_name,
    latitude,
    longitude,
    capacity,
    region_id,
    region_name,
    has_ebike_charging,
    nta_code,
    neighborhood,
    borough,
    location_method,
    first_seen_at,
    attributes_updated_at
from {{ ref('int_station_locations') }}

{% endsnapshot %}
