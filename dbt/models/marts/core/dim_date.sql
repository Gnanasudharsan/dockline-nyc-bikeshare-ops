-- Calendar dimension (local New York dates), 2025 through 2030.

with days as (

    select cast(day as date) as calendar_date
    from generate_series(date '2025-01-01', date '2030-12-31', interval '1 day') as day

)

select
    cast(to_char(calendar_date, 'YYYYMMDD') as integer) as date_key,
    calendar_date,
    cast(extract(year from calendar_date) as integer) as year,
    cast(extract(quarter from calendar_date) as integer) as quarter,
    cast(extract(month from calendar_date) as integer) as month,
    to_char(calendar_date, 'FMMonth') as month_name,
    to_char(calendar_date, 'Mon') as month_short_name,
    cast(extract(day from calendar_date) as integer) as day_of_month,
    cast(extract(isodow from calendar_date) as integer) as day_of_week,
    to_char(calendar_date, 'FMDay') as day_name,
    to_char(calendar_date, 'Dy') as day_short_name,
    extract(isodow from calendar_date) >= 6 as is_weekend,
    case when extract(isodow from calendar_date) >= 6 then 'Weekend' else 'Weekday' end
        as day_type,
    cast(date_trunc('week', calendar_date) as date) as week_start_date,
    cast(extract(week from calendar_date) as integer) as iso_week,
    cast(date_trunc('month', calendar_date) as date) as month_start_date
from days
