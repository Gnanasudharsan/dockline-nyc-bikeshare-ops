-- Pipeline events: run failures and failed checks from Dagster (and later other
-- services). Grafana reads this table as an annotation source (Phase 3), so every
-- alert is also visible as a marker on the live dashboards.

CREATE TABLE ops.pipeline_events (
    event_id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at    timestamptz NOT NULL DEFAULT now(),
    source         text        NOT NULL,
    event_type     text        NOT NULL
        CHECK (event_type IN ('run_failure', 'check_failure', 'check_warning', 'info')),
    severity       text        NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    title          text        NOT NULL,
    details        jsonb       NOT NULL DEFAULT '{}'::jsonb,
    dagster_run_id text
);

CREATE INDEX pipeline_events_occurred_at_idx ON ops.pipeline_events (occurred_at DESC);

COMMENT ON TABLE ops.pipeline_events IS
    'Operational alerts (failed runs, failed checks). Grafana annotation source.';
