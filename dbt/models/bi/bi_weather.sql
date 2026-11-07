{{ config(alias='weather') }}

-- Hourly weather. weather_hour_key = whole hours since 1970-01-01 UTC (integer join key).

select
    cast(extract(epoch from weather_hour) / 3600 as bigint) as weather_hour_key,
    {{ local_ts('weather_hour') }} as weather_hour_local,
    temperature_c,
    temperature_f,
    apparent_temperature_c,
    precipitation_mm,
    snowfall_cm,
    weather_condition,
    weather_description,
    temperature_band,
    temperature_band_order,
    is_precipitating,
    wind_speed_kmh,
    is_forecast
from {{ ref('dim_weather') }}
