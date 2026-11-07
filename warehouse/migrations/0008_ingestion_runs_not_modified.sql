-- Record polls answered with HTTP 304 Not Modified (conditional GET, ADR 0008).
-- These are healthy polls that found no new feed version, distinct from polls that
-- downloaded a payload whose stations had all reported before.
ALTER TABLE ops.ingestion_runs
    ADD COLUMN not_modified boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN ops.ingestion_runs.not_modified IS
    'True when the source answered 304 Not Modified to a conditional request.';
