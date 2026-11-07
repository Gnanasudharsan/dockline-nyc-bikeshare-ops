select
    run_id,
    feed,
    started_at,
    finished_at,
    status as run_status,
    not_modified,
    source_version,
    source_last_updated,
    records_fetched,
    records_inserted,
    records_duplicate,
    records_rejected,
    rejection_reasons,
    latency_ms,
    error_message
from {{ source('ops', 'ingestion_runs') }}
