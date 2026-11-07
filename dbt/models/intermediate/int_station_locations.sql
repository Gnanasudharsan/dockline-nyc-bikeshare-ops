{{ config(materialized='table') }}

-- Places every station in a borough and neighborhood.
--
-- The warehouse has no PostGIS, so neighborhoods are core Postgres polygons and the
-- match uses the built-in "contains" (@>) and "distance" (<->) operators.
-- Priority:
--   1. GBFS region with a fixed borough (Jersey City, Hoboken are outside NYC data).
--   2. The NYC neighborhood polygon that contains the station.
--   3. The nearest neighborhood within ~500 m (piers and shoreline stations fall just
--      outside the simplified, water-clipped polygons).
--   4. The area of the nearest already-placed station within ~1 km (a few NJ stations
--      are published without a region_id).
--   5. 'Unknown'.

with stations as (

    select * from {{ ref('stg_gbfs__station_information') }}

),

neighborhoods as (

    select
        nta_code,
        nta_name,
        borough,
        nta_type,
        cast(boundary as polygon) as boundary
    from {{ ref('nyc_neighborhoods') }}

),

regions as (

    select * from {{ ref('gbfs_regions') }}

),

contained as (

    select distinct on (stations.station_id)
        stations.station_id,
        neighborhoods.nta_code,
        neighborhoods.nta_name,
        neighborhoods.borough
    from stations
    inner join neighborhoods
        on neighborhoods.boundary @> point(stations.longitude, stations.latitude)
    -- Simplified polygons can overlap by a few meters; prefer residential areas.
    order by stations.station_id, neighborhoods.nta_type, neighborhoods.nta_code

),

nearest as (

    select distinct on (stations.station_id)
        stations.station_id,
        neighborhoods.nta_code,
        neighborhoods.nta_name,
        neighborhoods.borough
    from stations
    inner join neighborhoods
        on neighborhoods.boundary <-> point(stations.longitude, stations.latitude) < 0.005
    where not exists (
            select 1 from contained
            where contained.station_id = stations.station_id
        )
    order by
        stations.station_id,
        neighborhoods.boundary <-> point(stations.longitude, stations.latitude)

),

first_pass as (

    select
        stations.station_id,
        stations.short_name,
        stations.station_name,
        stations.latitude,
        stations.longitude,
        stations.capacity,
        stations.region_id,
        regions.region_name,
        stations.has_ebike_charging,
        case
            when regions.borough is not null then null
            else coalesce(contained.nta_code, nearest.nta_code)
        end as nta_code,
        coalesce(regions.neighborhood, contained.nta_name, nearest.nta_name) as neighborhood,
        coalesce(regions.borough, contained.borough, nearest.borough) as borough,
        case
            when regions.borough is not null then 'gbfs_region'
            when contained.station_id is not null then 'polygon'
            when nearest.station_id is not null then 'nearest_polygon'
        end as location_method,
        stations.first_seen_at,
        stations.last_seen_at,
        stations.attributes_updated_at
    from stations
    left join regions on stations.region_id = regions.region_id
    left join contained on stations.station_id = contained.station_id
    left join nearest on stations.station_id = nearest.station_id

)

select
    unplaced.station_id,
    unplaced.short_name,
    unplaced.station_name,
    unplaced.latitude,
    unplaced.longitude,
    unplaced.capacity,
    unplaced.region_id,
    unplaced.region_name,
    unplaced.has_ebike_charging,
    coalesce(unplaced.nta_code, neighbor.nta_code) as nta_code,
    coalesce(unplaced.neighborhood, neighbor.neighborhood, 'Unknown') as neighborhood,
    coalesce(unplaced.borough, neighbor.borough, 'Unknown') as borough,
    coalesce(
        unplaced.location_method,
        case when neighbor.borough is not null then 'nearest_station' end,
        'unmatched'
    ) as location_method,
    unplaced.first_seen_at,
    unplaced.last_seen_at,
    unplaced.attributes_updated_at
from first_pass as unplaced
left join lateral (
    select
        placed.nta_code,
        placed.neighborhood,
        placed.borough
    from first_pass as placed
    where
        unplaced.borough is null
        and placed.borough is not null
        and point(placed.longitude, placed.latitude)
        <-> point(unplaced.longitude, unplaced.latitude) < 0.01
    order by point(placed.longitude, placed.latitude) <-> point(unplaced.longitude, unplaced.latitude)
    limit 1
) as neighbor on true
