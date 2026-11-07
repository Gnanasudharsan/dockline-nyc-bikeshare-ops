# 0016. A 5-minute dbt build and time travel in Grafana

- Status: Accepted
- Date: 2026-11-07

## Context
Grafana must show live numbers and let an operator rewind to any past moment. The
station grid (ADR 0010) was rebuilt hourly, so rewinding to "20 minutes ago" would
have shown nothing.

## Decision
- **Live numbers** come from `fleet_status`, a view over the real-time Timescale
  aggregate, so they are as fresh as the last feed poll.
- A **`live_dbt_build`** Dagster job rebuilds only `int_station_status_5min_filled` and
  `fct_station_status_5min` (dbt tag `live`) two minutes after each 5-minute bucket
  closes (skipping :05, when the hourly build runs). Each run is incremental and takes
  seconds. Freshness policy: warn after 15 minutes, fail after 30.
- **Rewind:** history panels follow Grafana's time picker. The map shows the network at
  the end of the selected range: a `$at_bucket` variable (warehouse datasource) picks
  the last 5-minute bucket that is certainly built at that moment
  (`floor5(min(to, now)) − 10 minutes`).
- The public dashboard (for embedding) cannot use variables, so it shows the live map
  from `fleet_status` instead.

## Consequences
- Rewound views are at most about 10 minutes behind real time and exact for any past
  bucket within the 35-day 5-minute retention; older periods use hourly data.
- Dagster gains ~250 short runs a day; they are serialized with other dbt runs.
