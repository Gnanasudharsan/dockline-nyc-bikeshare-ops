{{ config(alias='date') }}

-- Calendar (marked as the date table in Power BI).

select
    date_key,
    calendar_date,
    year,
    quarter,
    month,
    month_name,
    month_short_name,
    day_of_month,
    day_of_week,
    day_name,
    day_short_name,
    is_weekend,
    day_type,
    week_start_date,
    month_start_date
from {{ ref('dim_date') }}
