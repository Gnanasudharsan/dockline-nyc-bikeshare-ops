-- One row per poll of a source feed. This is the audit log behind
-- "is ingestion healthy?" and the data_freshness_seconds metric.
CREATE TABLE ops.ingestion_runs (
    run_id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feed                text        NOT NULL
        CHECK (feed IN ('station_status', 'station_information', 'weather_hourly')),
    started_at          timestamptz NOT NULL DEFAULT now(),
    finished_at         timestamptz,
    status              text        NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'failed')),
    source_version      text,
    source_last_updated timestamptz,
    records_fetched     integer     NOT NULL DEFAULT 0 CHECK (records_fetched >= 0),
    records_inserted    integer     NOT NULL DEFAULT 0 CHECK (records_inserted >= 0),
    records_duplicate   integer     NOT NULL DEFAULT 0 CHECK (records_duplicate >= 0),
    records_rejected    integer     NOT NULL DEFAULT 0 CHECK (records_rejected >= 0),
    rejection_reasons   jsonb       NOT NULL DEFAULT '{}'::jsonb,
    latency_ms          integer     CHECK (latency_ms >= 0),
    error_message       text
);

CREATE INDEX ingestion_runs_feed_started_idx ON ops.ingestion_runs (feed, started_at DESC);

COMMENT ON TABLE ops.ingestion_runs IS 'Audit log: one row per poll of a source feed.';
COMMENT ON COLUMN ops.ingestion_runs.records_duplicate IS
    'Valid records already stored (station did not report a new last_reported).';
COMMENT ON COLUMN ops.ingestion_runs.latency_ms IS 'Wall time from fetch start to commit.';
