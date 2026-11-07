{% snapshot snap_daily_kpis %}

{{
    config(
        unique_key='kpi_id',
        strategy='check',
        check_cols='all',
        tags=['daily'],
    )
}}

-- "As-of" history of published daily KPIs. Only complete days are captured, so the
-- first version is what the KPI said when the day closed; a later version appears only
-- if late data restated it. dbt_valid_from is when each version was recorded.

select *
from {{ ref('fct_daily_kpis') }}
where is_complete_day

{% endsnapshot %}
