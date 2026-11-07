-- Hourly NYC weather. Hours still in the future are forecasts; they are overwritten
-- with observations by later ingestion runs.

select
    weather.observed_hour as weather_hour,
    weather.temperature_c,
    weather.apparent_temperature_c,
    weather.precipitation_mm,
    weather.rain_mm,
    weather.snowfall_cm,
    weather.weather_code,
    coalesce(codes.description, 'Unknown') as weather_description,
    coalesce(codes.weather_condition, 'Unknown') as weather_condition,
    weather.wind_speed_kmh,
    weather.relative_humidity_pct,
    weather.is_forecast,
    weather.fetched_at
from {{ source('open_meteo', 'weather_hourly') }} as weather
left join {{ ref('wmo_weather_codes') }} as codes
    on weather.weather_code = codes.weather_code
