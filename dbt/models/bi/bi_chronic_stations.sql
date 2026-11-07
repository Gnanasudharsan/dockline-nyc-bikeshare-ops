{{ config(alias='chronic_stations') }}

select
    station_key,
    chronic_status,
    chronic_problem_station,
    peak_hours_observed,
    peak_in_service_minutes,
    peak_empty_minutes,
    peak_full_minutes,
    peak_empty_share,
    peak_full_share,
    lookback_days
from {{ ref('mart_chronic_stations') }}
