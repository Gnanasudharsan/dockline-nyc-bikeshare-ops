{{ config(alias='station') }}

-- Station dimension for Power BI (SCD2 versions; facts join on station_key).
-- Timestamps are New York local time without a zone: Power BI has no timestamptz type.

select
    station_key,
    station_id,
    station_name,
    short_name,
    borough,
    neighborhood,
    capacity,
    latitude,
    longitude,
    has_ebike_charging,
    is_current,
    {{ local_ts('valid_from') }} as valid_from_local,
    {{ local_ts('valid_to') }} as valid_to_local
from {{ ref('dim_station') }}
