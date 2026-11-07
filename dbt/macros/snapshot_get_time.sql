{#-
    dbt-postgres stamps snapshot metadata with a timestamp *without* time zone (session
    local time). Every timestamp in this warehouse is timestamptz, so use now() instead;
    it keeps snapshot validity windows comparable with fact timestamps.
-#}
{% macro postgres__snapshot_get_time() -%}
    now()
{%- endmacro %}
