-- Time-of-day dimension at 5-minute grain (288 rows), local New York time.

with slots as (

    select
        cast(extract(hour from slot) as integer) as hour_of_day,
        cast(extract(minute from slot) as integer) as minute_of_hour
    from generate_series(
            timestamp '2000-01-01 00:00', timestamp '2000-01-01 23:55', interval '5 minutes'
        ) as slot

)

select
    hour_of_day * 100 + minute_of_hour as time_key,
    hour_of_day,
    minute_of_hour,
    lpad(cast(hour_of_day as text), 2, '0')
    || ':'
    || lpad(cast(minute_of_hour as text), 2, '0') as time_label,
    case
        when hour_of_day = 0 then '12 AM'
        when hour_of_day < 12 then hour_of_day || ' AM'
        when hour_of_day = 12 then '12 PM'
        else (hour_of_day - 12) || ' PM'
    end as hour_label,
    case
        when hour_of_day < 6 then 'Overnight'
        when hour_of_day < 10 then 'Morning'
        when hour_of_day < 16 then 'Midday'
        when hour_of_day < 20 then 'Evening'
        else 'Night'
    end as day_part,
    case
        when hour_of_day < 6 then 1
        when hour_of_day < 10 then 2
        when hour_of_day < 16 then 3
        when hour_of_day < 20 then 4
        else 5
    end as day_part_order,
    -- Peak applies on weekdays only; facts combine this with the date.
    hour_of_day in ({{ var('peak_hours') | join(', ') }}) as is_peak_hour
from slots
