{{ config(alias='borough') }}

-- One row per borough (plus Jersey City and Hoboken). Row-level security in Power BI
-- filters this table; the filter flows to stations and then to every fact.

select
    borough,
    case
        when borough in ('Jersey City', 'Hoboken') then 'New Jersey'
        when borough = 'Unknown' then 'Unknown'
        else 'New York City'
    end as city,
    case borough
        when 'Manhattan' then 1
        when 'Brooklyn' then 2
        when 'Queens' then 3
        when 'Bronx' then 4
        when 'Staten Island' then 5
        when 'Jersey City' then 6
        when 'Hoboken' then 7
        else 8
    end as borough_order
from (
    select distinct borough from {{ ref('dim_station') }}
) as boroughs
