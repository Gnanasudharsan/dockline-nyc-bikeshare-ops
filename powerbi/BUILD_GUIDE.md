# Build guide: the Dockline Power BI project

The whole Power BI project is **text generated on the Mac** by `build_pbip.py`. The
generator is the source of truth: open the project in Power BI Desktop to view and
verify it, but make lasting changes in the generator.

## Layout

```
powerbi/
  build_pbip.py               generator (model + report + theme + measures.md)
  Dockline.pbip               open this in Power BI Desktop
  Dockline.SemanticModel/     TMDL semantic model
    definition.pbism
    definition/
      database.tmdl, model.tmdl
      expressions.tmdl        DbHost / DbPort / DbName parameters
      relationships.tmdl
      tables/*.tmdl           8 DirectQuery tables + DAX measures
      roles/*.tmdl            row-level security, one role per borough
  Dockline.Report/            PBIR report
    definition.pbir           points at ../Dockline.SemanticModel
    definition/
      report.json             theme registration, report settings
      pages/<page>/page.json  5 pages (auto refresh on Live Operations, Rebalancing)
      pages/<page>/visuals/<visual>/visual.json
    StaticResources/RegisteredResources/Dockline.json   theme (copy of theme/dockline.json)
  theme/dockline.json         Dockline theme
  dax/measures.md             every measure, its DAX, and its Cube twin (generated)
  scripts/validate_pbip.py    schema, theme, and field-reference validation
  scripts/cube_reference_values.py   Cube numbers to compare in Desktop
  tools/tmdl-validator/       .NET 8 console app using Microsoft's TmdlSerializer
  VERIFY.md                   checklist for Power BI Desktop
```

## Data path

Power BI Desktop connects in **DirectQuery** with the `PostgreSQL.Database` connector:
`DbHost:DbPort / DbName`, schema `bi`. It logs in as `dockline_bi`, which can read only
the `bi` schema (migration 0011). The `bi` views are dbt models (`dbt/models/bi`) that
present the marts in a Power BI-friendly shape:
- timestamps as New York local time with no time zone (Power BI has no `timestamptz`)
- integer join keys
- a `borough` table for row-level security

An integration test checks that every `bi` view has exactly the columns and types the
TMDL declares.

## Semantic model

| Table | Source view | Role |
| --- | --- | --- |
| `fleet_status` | `bi.fleet_status` | Live station state; measures mirror Cube `fleet_status` |
| `station_hourly` | `bi.station_hourly` | Hourly history; measures mirror Cube `station_hourly` |
| `chronic_stations` | `bi.chronic_stations` | 14-day weekday-peak verdicts; mirrors Cube `chronic_stations` |
| `Station` | `bi.station` | Station versions (SCD2), joined on `station_key` |
| `Borough` | `bi.borough` | Borough list; row-level security filters this table |
| `Date` | `bi.date` | Calendar, marked as the date table |
| `Hour` | `bi.hour` | Local hour of day |
| `Weather` | `bi.weather` | Hourly weather; measures mirror Cube `weather` |

Filters flow `Borough → Station → facts`, so one row-level security filter on `Borough`
secures every page. Implicit measures are off (`discourageImplicitMeasures`): every
number on a visual is a named measure with the same name and meaning as in Cube. See
[`dax/measures.md`](dax/measures.md) and [`../docs/metrics.md`](../docs/metrics.md).

## Change something

1. Edit `build_pbip.py`:
   - columns and measures: `TABLES`
   - joins: `RELATIONSHIPS`
   - report: `PAGES`
   - colors and fonts: `theme()`
2. Regenerate and validate:

   ```bash
   make powerbi
   ```

   ```bash
   make powerbi-validate
   ```

   ```bash
   uv run pytest tests/test_powerbi.py
   ```

3. If you add a column, add it to the matching `dbt/models/bi` view too. The integration
   test fails until both agree.
4. If you add a measure that is a certified metric, define it in Cube first, under the
   same name. `tests/test_powerbi.py` fails for a DAX measure with no Cube twin.

If you change something in Desktop (for example, to try a layout), save it, look at the
diff, and port the change into `build_pbip.py`. Otherwise the next `make powerbi`
overwrites it, and the test that compares the committed files with the generator fails.

## Fonts

The theme asks for **Archivo** and falls back to Segoe UI. To match the design system,
install Archivo from Google Fonts in the VM; it is a free, open font.

## Manual page specs

Use these only if a generated page fails to render in Desktop twice (VERIFY.md, step 8).
Canvas: 1280 × 720, fit to page, Dockline theme. Positions are x, y, width, height.

### Executive Summary
| Visual | Type | Fields | Position |
| --- | --- | --- | --- |
| Availability rate | Card | `station_hourly[availability_rate]` | 20, 20, 200, 110 |
| Empty share | Card | `[empty_share]` | 230, 20, 200, 110 |
| Full share | Card | `[full_share]` | 440, 20, 200, 110 |
| Bikes added | Card | `[bikes_added]` | 650, 20, 200, 110 |
| Chronic problem stations | Card | `chronic_stations[chronic_problem_stations]` | 860, 20, 200, 110 |
| Date | Slicer (between) | `Date[calendar_date]` | 1070, 20, 190, 110 |
| Availability rate by day and borough | Line chart | X `Date[calendar_date]`, Y `[availability_rate]`, Legend `Borough[borough]` | 20, 150, 760, 330 |
| Availability rate by borough | Clustered bar | Y-axis `Borough[borough]`, X `[availability_rate]`, sort ascending | 800, 150, 460, 330 |
| Empty and full share by hour of day | Clustered column | X `Hour[hour_label]`, Y `[empty_share]`, `[full_share]` | 20, 500, 1240, 200 |

### Live Operations (page refresh on, 30 s)
| Visual | Type | Fields | Position |
| --- | --- | --- | --- |
| Bikes / E-bikes / Docks available, Empty / Full stations, Stations in service, Data age (s) | 7 cards | `fleet_status[bikes_available]`, `[ebikes_available]`, `[docks_available]`, `[empty_stations]`, `[full_stations]`, `[stations_in_service]`, `[data_freshness_seconds]` | y 20, height 110, x every 180 |
| Stations by imbalance state | Clustered bar | `fleet_status[imbalance_state]`, `[stations]` | 20, 150, 520, 260 |
| Right now by borough | Table | `Borough[borough]`, `[bikes_available]`, `[docks_available]`, `[fill_ratio]`, `[empty_stations]`, `[full_stations]`, `[offline_stations]` | 560, 150, 700, 260 |
| High-traffic stations with no bikes | Table | `Station[station_name]`, `Borough[borough]`, `fleet_status[is_high_traffic]`, `[longest_empty_minutes]`, `[empty_stations]`; sort by longest empty descending; filter state ≠ offline | 20, 430, 1240, 270 |

### Station Performance
| Visual | Type | Fields | Position |
| --- | --- | --- | --- |
| Borough | Slicer (list) | `Borough[borough]` | 20, 20, 240, 200 |
| Date | Slicer (between) | `Date[calendar_date]` | 20, 240, 240, 110 |
| Stations by availability | Table | `Station[station_name]`, `Station[neighborhood]`, `[availability_rate]`, `[empty_share]`, `[full_share]`, `[bikes_added]`, `[bikes_removed]`, `[net_flow]`; sort availability ascending | 280, 20, 980, 420 |
| Chronic verdicts | Table | `Station[station_name]`, `chronic_stations[chronic_status]`, `[peak_hours_observed]`, `[peak_empty_share]`, `[peak_full_share]`; filter status ≠ insufficient_data | 280, 460, 980, 240 |
| Stations with a verdict / Chronic problem stations | 2 cards | `[stations_rated]`, `[chronic_problem_stations]` | 20, 370 and 20, 500 (240 × 110) |

### Weather Impact
| Visual | Type | Fields | Position |
| --- | --- | --- | --- |
| Average temperature, Precipitation, Availability rate | 3 cards | `Weather[avg_temperature_c]`, `Weather[total_precipitation_mm]`, `[availability_rate]` | y 20, 300 wide |
| Date | Slicer | `Date[calendar_date]` | 980, 20, 280, 110 |
| Availability by weather condition | Clustered bar | `Weather[weather_condition]`, `[availability_rate]` | 20, 150, 610, 270 |
| Availability by temperature band | Clustered column | `Weather[temperature_band]` (sorted by band order), `[availability_rate]` | 650, 150, 610, 270 |
| Bikes added and removed by condition | Clustered column | `Weather[weather_condition]`, `[bikes_added]`, `[bikes_removed]` | 20, 440, 1240, 260 |

### Rebalancing (page refresh on, 60 s)
| Visual | Type | Fields | Position |
| --- | --- | --- | --- |
| Starving / Flooding stations, Bikes to move, Network fill ratio | 4 cards | `[starving_stations]`, `[flooding_stations]`, `[rebalance_need_bikes]`, `[fill_ratio]` | y 20 |
| Borough | Slicer | `Borough[borough]` | 1040, 20, 220, 110 |
| Visit next | Table | `fleet_status[priority_rank]`, `Station[station_name]`, `Borough[borough]`, `fleet_status[recommended_action]`, `[bikes_to_move]`, `[imbalance_state]`, `[station_fill_ratio]` (columns, don't summarize); sort rank ascending; filter action ≠ "No action" | 20, 150, 820, 550 |
| Bikes to move by borough and state | Clustered bar | Y-axis `Borough[borough]`, X `[rebalance_need_bikes]`, Legend `fleet_status[imbalance_state]` | 860, 150, 400, 550 |

State colors (theme data colors and conditional formatting):
- starving: `#E0701F`
- balanced: `#A9B3C1`
- flooding: `#2357C6`
- offline: `#7A6F9B`

Always show the state name as a label next to the color.
