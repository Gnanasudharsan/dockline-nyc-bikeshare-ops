-- One row per station currently or previously listed in station_information.

select
    station_id,
    short_name,
    name as station_name,
    lat as latitude,
    lon as longitude,
    capacity,
    region_id,
    coalesce(has_ebike_charging, false) as has_ebike_charging,
    first_seen_at,
    last_seen_at,
    updated_at as attributes_updated_at
from {{ source('gbfs', 'station_information') }}
