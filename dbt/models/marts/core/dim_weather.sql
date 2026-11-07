-- Hourly weather dimension. Key: weather_hour (UTC hour start), joined from facts on
-- the hour their bucket falls in.

select
    weather_hour,
    temperature_c,
    round(cast(temperature_c * 9.0 / 5.0 + 32 as numeric), 1) as temperature_f,
    apparent_temperature_c,
    precipitation_mm,
    rain_mm,
    snowfall_cm,
    weather_code,
    weather_description,
    weather_condition,
    coalesce(precipitation_mm, 0) > 0 as is_precipitating,
    case
        when temperature_c is null then 'Unknown'
        when temperature_c < 0 then 'Freezing (below 0 °C)'
        when temperature_c < 10 then 'Cold (0–10 °C)'
        when temperature_c < 20 then 'Mild (10–20 °C)'
        when temperature_c < 28 then 'Warm (20–28 °C)'
        else 'Hot (28 °C and above)'
    end as temperature_band,
    case
        when temperature_c is null then 0
        when temperature_c < 0 then 1
        when temperature_c < 10 then 2
        when temperature_c < 20 then 3
        when temperature_c < 28 then 4
        else 5
    end as temperature_band_order,
    wind_speed_kmh,
    relative_humidity_pct,
    is_forecast,
    fetched_at
from {{ ref('stg_open_meteo__weather_hourly') }}
