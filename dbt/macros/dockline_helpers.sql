{#- Shared SQL snippets. Each returns a SQL expression, not a query. -#}

{% macro as_of_timestamp() -%}
    {#- "Now" for the run: the as_of var when set (tests, backfills), else the DB clock. -#}
    {%- if var('as_of') -%}
        cast('{{ var("as_of") }}' as timestamptz)
    {%- else -%}
        now()
    {%- endif -%}
{%- endmacro %}

{% macro bucket_5min(ts) -%}
    {#- Start of the 5-minute bucket containing ts (same alignment as the Timescale CAGG). -#}
    date_bin(interval '5 minutes', {{ ts }}, timestamptz '2000-01-01 00:00:00+00')
{%- endmacro %}

{% macro local_ts(ts) -%}
    ({{ ts }} at time zone '{{ var("local_timezone") }}')
{%- endmacro %}

{% macro date_key(ts) -%}
    {#- yyyymmdd integer of the local calendar date. -#}
    cast(to_char({{ local_ts(ts) }}, 'YYYYMMDD') as integer)
{%- endmacro %}

{% macro is_peak_period(ts) -%}
    {#- Weekday commute peak in local time. -#}
    (
        extract(isodow from {{ local_ts(ts) }}) < 6
        and extract(hour from {{ local_ts(ts) }}) in ({{ var('peak_hours') | join(', ') }})
    )
{%- endmacro %}

{% macro safe_divide(numerator, denominator) -%}
    ({{ numerator }})::numeric / nullif({{ denominator }}, 0)
{%- endmacro %}

{% macro prune_older_than(column, days) -%}
    {#- Post-hook: delete rows older than the retention window from this model. -#}
    delete from {{ this }}
    where {{ column }} < {{ as_of_timestamp() }} - interval '{{ days }} days'
{%- endmacro %}
