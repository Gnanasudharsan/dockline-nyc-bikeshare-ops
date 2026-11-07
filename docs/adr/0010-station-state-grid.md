# 0010. A carried-forward 5-minute station state grid

- Status: Accepted
- Date: 2026-11-07

## Context
`raw.station_status` stores a row only when a station reports something new
(ADR 0006), and the 5-minute continuous aggregate only has buckets that contained a
report. Metrics such as `empty_station_minutes` and `availability_rate` are
time-weighted: they need the station's state for every interval, including quiet ones.
Live data shows healthy stations report every ~100 s and none went more than 30
minutes without a report overnight.

## Decision
- `int_station_status_5min_filled` builds the full station × 5-minute grid and carries
  each station's last report forward ("last observation carried forward"), using a
  running count of reports as a group id and `first_value` within each group.
- A row's state is the station's state **at the end of the bucket**, and each row
  counts as 5 station-minutes. Minute metrics therefore have 5-minute resolution.
- A station is **offline** for a bucket when it has never reported, has not reported for
  more than 30 minutes (`stale_report_minutes`), is not installed, or is neither renting
  nor returning. Empty/full/available minutes only count while in service.
- The grid only covers the time a station is listed in `station_information`
  (from `first_seen_at` to two hours after `last_seen_at`).
- Incremental runs rebuild the last 3 hours (`status_lookback_hours`) to absorb late
  reports, seeding each station from the model's own row just before the window. A full
  refresh seeds from the aggregate instead. Both paths produce identical rows (verified
  by hashing the table after each).
- 5-minute facts are kept 35 days (`fact_5min_retention_days`); hourly and daily facts
  are kept forever. The Timescale aggregates remain the long-term 5-minute history.

## Consequences
- Every time-weighted metric is a plain `sum()` over additive minute columns, so Cube,
  Grafana, and Power BI can aggregate them at any grain without re-deriving state.
- Changes within a bucket are summarized by min/max columns but do not add minutes;
  a station empty for 2 minutes and refilled before the bucket ends is not counted.
- Thresholds live in `dbt_project.yml` vars and can be tuned without code changes.
