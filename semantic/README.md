# semantic

Cube Core data model: **the only place Dockline metrics are defined** (ADR 0003).
Grafana, the API, and the website all ask Cube; Power BI mirrors these definitions
measure-for-measure (Phase 4). Human-readable contract: [`docs/metrics.md`](../docs/metrics.md).

| Cube | Source | Use |
| --- | --- | --- |
| `fleet_status` | `marts.mart_rebalancing_recommendations` (live view) | "Right now" numbers, live map, rebalancing board, alerts. Refresh: 10 s. |
| `station_status` | `marts.fct_station_status_5min` | 5-minute history and rewind. Pre-aggregation `by_borough_5min`. |
| `station_hourly` | `marts.fct_station_hourly` | Hour-of-day, weather, weekday patterns. Pre-aggregation `by_borough_hour`. |
| `daily_kpis` | `marts.fct_daily_kpis` | Daily review by borough. |
| `chronic_stations` | `marts.mart_chronic_stations` | Chronic problem stations. |
| `stations`, `weather`, `dates` | dimensions | Joined from the fact cubes. |

Conventions:
- Ratios (`fill_ratio`, `availability_rate`, shares) are `number` measures dividing two
  additive sums, so they are correct at any grouping and inside rollups.
- Point-in-time totals (`bikes_available`, ...) only count in-service stations. On the
  5-minute cube, group by `bucket_start` at minute granularity.

## Query it

- REST: `http://localhost:4000/cubejs-api/v1/load` (JWT signed with `CUBEJS_API_SECRET`).
- SQL API (Postgres protocol): `psql -h localhost -p 15432 -U $CUBEJS_SQL_USER db`, then
  `SELECT borough, MEASURE(availability_rate) FROM daily_kpis GROUP BY 1;`

Design notes: [ADR 0014](../docs/adr/0014-grafana-reads-metrics-through-cube.md),
[ADR 0015](../docs/adr/0015-cube-deployment.md).
