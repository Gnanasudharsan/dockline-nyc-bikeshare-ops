# 0006. Store each distinct station report, keyed by last_reported

- Status: Accepted
- Date: 2026-11-07

## Context
`station_status` is polled every 60 s and lists all ~2,500 stations each time. Storing
every station on every poll would duplicate data whenever a station has not sent a new
report. GBFS gives each record a `last_reported` time, which is when the station itself
last reported, not when we fetched it.

## Decision
- Partition `raw.station_status` by `last_reported` (1-day chunks) and make
  `(station_id, last_reported)` unique. Inserts use `ON CONFLICT DO NOTHING`, so a poll
  only adds stations that reported something new. `fetched_at` is stored too.
- Reject placeholder timestamps (before 2013, such as `86400` for inactive stations) and
  timestamps more than 10 minutes in the future. Rejections are counted by reason in
  `ops.ingestion_runs.rejection_reasons`.
- Continuous aggregates take the *last* value per 5-minute bucket and per hour, plus
  min/max, so a bucket reflects the station's state at the end of the interval.
- Aggregate refresh windows (3 days) stay far inside raw retention (30 days), so
  dropping old raw chunks never erases aggregate history.

## Consequences
- No duplicates by construction; storage scales with real change, not poll count.
- A station that does not report during a 5-minute bucket has no row for that bucket.
  Time-weighted metrics (`empty_station_minutes`, `availability_rate`) must carry the
  last known state forward ("last observation carried forward") in dbt (Phase 2).
- The audit log separates "nothing new" (`records_duplicate`) from "bad data"
  (`records_rejected`), so a quiet feed is never mistaken for a broken one.
