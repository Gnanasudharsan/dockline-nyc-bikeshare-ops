# Metrics catalog

The certified metric definitions live in exactly one place: the Cube data model
(`semantic/model/cubes/`). This catalog is their human-readable contract. Cube
aggregates columns of the dbt marts and never re-derives station state. Grafana, the
API, and the website query Cube; Power BI mirrors these measures under the same names.

| Metric | Cube measure(s) |
| --- | --- |
| `bikes_available`, `ebikes_available`, `docks_available`, `fill_ratio`, `imbalance_index` | `fleet_status.*` (live), `station_status.*` (5-minute history) |
| `empty_station_minutes`, `full_station_minutes`, `availability_rate`, `net_flow` | `station_status.*`, `station_hourly.*`, `daily_kpis.*` |
| `rebalance_need_bikes` | `fleet_status.rebalance_need_bikes`, `station_status.rebalance_need_bikes` |
| `chronic_problem_station` | `chronic_stations.chronic_problem_stations` (count) |
| `data_freshness_seconds` | `fleet_status.data_freshness_seconds` |

- **Owner of all metrics:** Dockline operations analytics (Gnanasudharsan Ashokumar).
- **Time zone:** America/New_York for dates, hours of day, and peak periods.
- **Time resolution:** state is sampled at the end of each 5-minute bucket, and each
  bucket counts as 5 station-minutes (ADR 0010).
- **In service** means the station has reported in the last 30 minutes, is installed,
  and is renting or returning. All other station-minutes are **offline**.

## Point-in-time metrics

| Metric | Business definition | Formula | Grain | Source column | Caveats |
| --- | --- | --- | --- | --- | --- |
| `bikes_available` | Bikes a rider could rent right now | `num_bikes_available` from the latest report | station × moment | `fct_station_status_5min.bikes_available` | Includes e-bikes. Excludes disabled bikes. |
| `ebikes_available` | E-bikes a rider could rent right now | `num_ebikes_available` | station × moment | `…ebikes_available` | Subset of `bikes_available`. |
| `docks_available` | Empty docks a rider could return to | `num_docks_available` | station × moment | `…docks_available` | Excludes disabled docks. |
| `fill_ratio` | How full a station is | `bikes_available / (bikes_available + docks_available)` | station × moment | `…fill_ratio` | Null while offline or with no usable slots. Disabled slots are ignored. |
| `imbalance_index` | Signed distance from the target fill | `fill_ratio − target_fill_ratio` (target 0.5) | station × moment | `…imbalance_index` | Negative = starving, positive = flooding. |
| `imbalance_state` | Operational category for maps and boards | offline if not in service; starving if `bikes = 0` or `fill ≤ 0.2`; flooding if `docks = 0` or `fill ≥ 0.8`; else balanced | station × moment | `…imbalance_state` | Thresholds are dbt vars. Shown with fixed colors and labels everywhere. |
| `rebalance_need_bikes` | Bikes to add (+) or remove (−) to reach the target fill | `round(0.5 × (bikes + docks)) − bikes` | station × moment | `…rebalance_need_bikes`, `mart_rebalancing_recommendations` | Ignores where a truck can actually stop. Recommendations are made only for starving or flooding stations. |
| `data_freshness_seconds` | How old the newest station report is | `now() − max(last_reported)` | network | `raw.station_status` (Phase 3 Cube measure) | The feed itself lags 13–35 s behind real time (CDN). |

## Time-weighted metrics (additive minutes)

| Metric | Business definition | Formula | Grain | Source column | Caveats |
| --- | --- | --- | --- | --- | --- |
| `empty_station_minutes` | Minutes stations had no bike to rent while renting | `sum(5 if in service and renting and bikes = 0)` | any; additive | `empty_minutes` (5-min, hourly), `empty_station_minutes` (daily) | 5-minute resolution. |
| `full_station_minutes` | Minutes stations had no free dock while returning | `sum(5 if in service and returning and docks = 0)` | any; additive | `full_minutes`, `full_station_minutes` | 5-minute resolution. |
| `availability_rate` | Share of in-service station-minutes where a rider could both rent and return | `available minutes / in-service minutes`, where available = ≥1 bike and ≥1 dock and renting and returning | any; recompute from sums | `available_minutes`, `in_service_minutes`, `fct_daily_kpis.availability_rate` | Never average the rates; sum the minutes and divide. |
| `net_flow` | Change in bikes on hand per interval (demand proxy) | `bikes_available − previous bucket's bikes_available` | station × 5 min / hour | `net_flow_bikes`, `bikes_added`, `bikes_removed` | Rebalancing trucks also move bikes, so this is not trips. |

## Derived classifications

| Metric | Business definition | Formula | Grain | Source | Caveats |
| --- | --- | --- | --- | --- | --- |
| `chronic_problem_station` | Station that is regularly empty or full during weekday commutes | Over the trailing 14 days: peak empty minutes ÷ peak in-service minutes > 25%, or the same for full | station | `mart_chronic_stations` | Needs ≥ 10 observed peak hours, otherwise `insufficient_data`. Peaks are weekdays 7–10 and 16–20 local time. |
| rebalancing priority | Order in which to visit starving and flooding stations | `bikes_to_move × (1 + ln(1 + typical hourly turnover at this hour))` | station | `mart_rebalancing_recommendations` | Turnover = average bikes added + removed in the same local hour over the last 14 days. |

## Dimensions

| Dimension | Values | Source |
| --- | --- | --- |
| Station | name, short name, capacity, e-bike charging; SCD2 history | `dim_station` |
| Borough / neighborhood | Manhattan, Brooklyn, Queens, Bronx, Staten Island, Jersey City, Hoboken; NYC 2020 NTAs | `dim_station` (ADR 0011) |
| Hour of day, day part | 0–23; Overnight, Morning, Midday, Evening, Night | `dim_time`, `hour_of_day` |
| Day of week, weekday/weekend | ISO day of week; Weekday / Weekend | `dim_date` |
| Peak / off-peak | Weekday 7–10 and 16–20 local time | `is_peak_period` |
| Weather condition | Clear, Cloudy, Fog, Drizzle, Rain, Snow, Thunderstorm | `dim_weather` (WMO codes) |
| Temperature band | Freezing (below 0 °C), Cold (0–10 °C), Mild (10–20 °C), Warm (20–28 °C), Hot (28 °C and above) | `dim_weather` |
