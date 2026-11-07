# Architecture Decision Records

Short records of meaningful choices: context, decision, consequences.
New ADRs use the next number and the template in `0000-template.md`.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-timescaledb-warehouse.md) | PostgreSQL + TimescaleDB as the warehouse | Accepted |
| [0003](0003-cube-semantic-layer.md) | Cube Core as the single metrics layer | Accepted |
| [0004](0004-grafana-and-power-bi.md) | Grafana for live ops, Power BI for analysis | Accepted |
| [0005](0005-gbfs-discovery-and-version.md) | Resolve GBFS feeds via discovery, prefer v2.3 | Accepted |
| [0006](0006-raw-station-status-storage.md) | Store each distinct station report, keyed by last_reported | Accepted |
| [0007](0007-in-house-migration-runner.md) | A small in-house SQL migration runner | Accepted |
| [0008](0008-poll-on-feed-clock.md) | Schedule station_status polls from the feed's clock | Accepted |
| [0009](0009-conditional-requests.md) | Conditional requests for station_status | Accepted |
