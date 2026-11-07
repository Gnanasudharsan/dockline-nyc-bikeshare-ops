{{ config(alias='hour') }}

-- Hour-of-day dimension (local time), 24 rows.

select
    hour_of_day,
    hour_label,
    day_part,
    day_part_order,
    is_peak_hour
from {{ ref('dim_time') }}
where minute_of_hour = 0
