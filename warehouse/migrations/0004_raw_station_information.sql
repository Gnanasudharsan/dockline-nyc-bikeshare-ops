-- Current attributes of each station from GBFS station_information.
-- Upserted hourly; updated_at changes only when an attribute actually changes.
-- dbt snapshots this table into an SCD2 dimension (Phase 2).
CREATE TABLE raw.station_information (
    station_id          text             PRIMARY KEY,
    short_name          text,
    name                text             NOT NULL,
    lat                 double precision NOT NULL CHECK (lat BETWEEN -90 AND 90),
    lon                 double precision NOT NULL CHECK (lon BETWEEN -180 AND 180),
    capacity            smallint         CHECK (capacity >= 0),
    region_id           text,
    has_ebike_charging  boolean,
    first_seen_at       timestamptz      NOT NULL,
    last_seen_at        timestamptz      NOT NULL,
    updated_at          timestamptz      NOT NULL,
    ingestion_run_id    bigint           NOT NULL
);

COMMENT ON TABLE raw.station_information IS
    'Latest known attributes per station. last_seen_at = last time the feed listed it.';
