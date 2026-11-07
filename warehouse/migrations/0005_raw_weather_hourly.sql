-- Hourly NYC weather from Open-Meteo. Recent hours are revised by the provider,
-- so rows are upserted on observed_hour. is_forecast marks hours still in the future
-- at fetch time.
CREATE TABLE raw.weather_hourly (
    observed_hour           timestamptz      PRIMARY KEY,
    temperature_c           real,
    apparent_temperature_c  real,
    precipitation_mm        real             CHECK (precipitation_mm >= 0),
    rain_mm                 real             CHECK (rain_mm >= 0),
    snowfall_cm             real             CHECK (snowfall_cm >= 0),
    weather_code            smallint,
    wind_speed_kmh          real             CHECK (wind_speed_kmh >= 0),
    relative_humidity_pct   real             CHECK (relative_humidity_pct BETWEEN 0 AND 100),
    is_forecast             boolean          NOT NULL,
    fetched_at              timestamptz      NOT NULL,
    ingestion_run_id        bigint           NOT NULL
);

COMMENT ON COLUMN raw.weather_hourly.weather_code IS 'WMO weather interpretation code.';
