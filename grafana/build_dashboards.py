"""Generate the Dockline Grafana dashboards (grafana/dashboards/*.json).

Dashboards are code: edit this file, run ``make grafana-dashboards``, commit both.
A test (tests/test_grafana.py) fails if the JSON is out of date.

Rules this builder enforces:
* Every metric comes from Cube (datasource ``cube``) via ``MEASURE(...)``. The
  warehouse datasource is only used for alert annotations and the time-travel variable.
* Imbalance states always use the same colors and are always labelled
  (starving, balanced, flooding, offline), never color alone.
* Live numbers refresh every 10 seconds.

Usage: ``python3 grafana/build_dashboards.py`` (stdlib only).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).resolve().parent / "dashboards"

CUBE = {"type": "grafana-postgresql-datasource", "uid": "cube"}
WAREHOUSE = {"type": "grafana-postgresql-datasource", "uid": "warehouse"}

# Dockline design system (CLAUDE.md): fixed data colors and the signal color.
STATE_COLORS = {
    "starving": "#E0701F",
    "balanced": "#A9B3C1",
    "flooding": "#2357C6",
    "offline": "#7A6F9B",
}
SIGNAL = "#1B5FD1"
INK_SLATE = "#4A5A6E"

Panel = dict[str, Any]


# ---------------------------------------------------------------- building blocks


def query(
    sql: str, ref: str = "A", fmt: str = "table", datasource: dict[str, str] = CUBE
) -> dict[str, Any]:
    """A raw-SQL target for a Postgres-protocol datasource."""
    return {
        "refId": ref,
        "datasource": datasource,
        "editorMode": "code",
        "rawQuery": True,
        "format": fmt,
        "rawSql": " ".join(sql.split()),
    }


def grid(x: int, y: int, w: int, h: int) -> dict[str, int]:
    """Panel position on Grafana's 24-column grid."""
    return {"x": x, "y": y, "w": w, "h": h}


def fixed_color(color: str) -> dict[str, Any]:
    """Field color config with one fixed color."""
    return {"mode": "fixed", "fixedColor": color}


def state_value_mappings() -> list[dict[str, Any]]:
    """Map imbalance-state strings to their fixed colors (text stays visible)."""
    return [
        {
            "type": "value",
            "options": {
                state: {"text": state, "color": color, "index": index}
                for index, (state, color) in enumerate(STATE_COLORS.items())
            },
        }
    ]


def state_series_overrides() -> list[dict[str, Any]]:
    """Color series named after an imbalance state with that state's color."""
    return [
        {
            "matcher": {"id": "byName", "options": state},
            "properties": [{"id": "color", "value": fixed_color(color)}],
        }
        for state, color in STATE_COLORS.items()
    ]


def stat(
    title: str,
    sql: str,
    pos: dict[str, int],
    *,
    unit: str = "none",
    decimals: int | None = 0,
    description: str = "",
    thresholds: list[dict[str, Any]] | None = None,
    color: str = SIGNAL,
) -> Panel:
    """A single-number panel. Uses tabular numbers via Grafana's default font."""
    steps = thresholds or [{"color": color, "value": None}]
    return {
        "type": "stat",
        "title": title,
        "description": description,
        "gridPos": pos,
        "datasource": CUBE,
        "targets": [query(sql)],
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "auto",
            "textMode": "value",
            "wideLayout": True,
        },
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "decimals": decimals,
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": steps},
            },
            "overrides": [],
        },
    }


def timeseries(
    title: str,
    targets: list[dict[str, Any]],
    pos: dict[str, int],
    *,
    unit: str = "none",
    description: str = "",
    stacked: bool = False,
    overrides: list[dict[str, Any]] | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
    target_line: float | None = None,
    points: bool = False,
) -> Panel:
    """A time-series panel; long-format results (time, metric, value) become series."""
    defaults: dict[str, Any] = {
        "unit": unit,
        "color": {"mode": "palette-classic"},
        "custom": {
            "drawStyle": "line",
            "lineWidth": 2,
            "fillOpacity": 60 if stacked else 8,
            "showPoints": "always" if points else "never",
            "pointSize": 6,
            "spanNulls": False,
            "stacking": {"mode": "normal" if stacked else "none", "group": "A"},
            "axisBorderShow": False,
        },
    }
    if min_value is not None:
        defaults["min"] = min_value
    if max_value is not None:
        defaults["max"] = max_value
    if target_line is not None:
        defaults["thresholds"] = {
            "mode": "absolute",
            "steps": [
                {"color": "transparent", "value": None},
                {"color": INK_SLATE, "value": target_line},
            ],
        }
        defaults["custom"]["thresholdsStyle"] = {"mode": "dashed"}
    return {
        "type": "timeseries",
        "title": title,
        "description": description,
        "gridPos": pos,
        "datasource": CUBE,
        "targets": targets,
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "fieldConfig": {"defaults": defaults, "overrides": overrides or []},
    }


def table(
    title: str,
    sql: str,
    pos: dict[str, int],
    *,
    description: str = "",
    overrides: list[dict[str, Any]] | None = None,
) -> Panel:
    """A table panel."""
    return {
        "type": "table",
        "title": title,
        "description": description,
        "gridPos": pos,
        "datasource": CUBE,
        "targets": [query(sql)],
        "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
        "fieldConfig": {
            "defaults": {"custom": {"align": "auto", "cellOptions": {"type": "auto"}}},
            "overrides": overrides or [],
        },
    }


def bar_chart(
    title: str,
    sql: str,
    pos: dict[str, int],
    *,
    color_by_field: str | None = None,
    unit: str = "none",
    description: str = "",
    horizontal: bool = False,
    stacked: bool = False,
    overrides: list[dict[str, Any]] | None = None,
    max_value: float | None = None,
) -> Panel:
    """A categorical bar chart (first string column = categories)."""
    defaults: dict[str, Any] = {
        "unit": unit,
        "color": fixed_color(SIGNAL),
        "custom": {"fillOpacity": 85, "lineWidth": 0},
    }
    if max_value is not None:
        defaults["max"] = max_value
    return {
        "type": "barchart",
        "title": title,
        "description": description,
        "gridPos": pos,
        "datasource": CUBE,
        "targets": [query(sql)],
        "options": {
            "orientation": "horizontal" if horizontal else "vertical",
            "stacking": "normal" if stacked else "none",
            "showValue": "auto",
            "xTickLabelRotation": 0,
            **({"colorByField": color_by_field} if color_by_field else {}),
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi"},
        },
        "fieldConfig": {
            "defaults": defaults,
            "overrides": [
                *(overrides or []),
                # The category column (hour, borough, ...) never takes the value unit.
                {
                    "matcher": {"id": "byName", "options": "hour"},
                    "properties": [{"id": "unit", "value": "none"}],
                },
            ],
        },
    }


STATE_KEY = "orange = starving · gray = balanced · blue = flooding · purple = offline"


def station_map(title: str, sql: str, pos: dict[str, int], *, description: str = "") -> Panel:
    """Geomap of station dots colored (and labelled in the tooltip) by imbalance state.

    The query must return latitude, longitude, state, plus any tooltip fields. The
    color key is part of the title, so color is never the only cue.
    """
    return {
        "type": "geomap",
        "title": f"{title} ({STATE_KEY})",
        "description": description,
        "gridPos": pos,
        "datasource": CUBE,
        "targets": [query(sql)],
        "options": {
            "view": {"id": "coords", "lat": 40.735, "lon": -73.96, "zoom": 11.2},
            "controls": {"showZoom": True, "mouseWheelZoom": True, "showAttribution": True},
            "tooltip": {"mode": "details"},
            # Grafana's geomap needs raster tiles; OpenFreeMap serves vector tiles only, so
            # dashboards use Grafana's built-in light basemap (the website uses OpenFreeMap).
            "basemap": {
                "type": "carto",
                "name": "Basemap",
                "config": {"theme": "light", "showLabels": True},
            },
            "layers": [
                {
                    "type": "markers",
                    "name": "Stations",
                    "location": {
                        "mode": "coords",
                        "latitude": "latitude",
                        "longitude": "longitude",
                    },
                    "config": {
                        "showLegend": False,
                        "style": {
                            "color": {"field": "state", "fixed": STATE_COLORS["balanced"]},
                            "size": {"fixed": 4},
                            "opacity": 0.85,
                            "symbol": {"mode": "fixed", "fixed": "img/icons/marker/circle.svg"},
                        },
                    },
                    "tooltip": True,
                }
            ],
        },
        "fieldConfig": {
            "defaults": {"color": {"mode": "thresholds"}},
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "state"},
                    "properties": [
                        {"id": "mappings", "value": state_value_mappings()},
                        {
                            "id": "color",
                            "value": {"mode": "fixed", "fixedColor": STATE_COLORS["balanced"]},
                        },
                    ],
                }
            ],
        },
    }


def text(content: str, pos: dict[str, int]) -> Panel:
    """A markdown note."""
    return {
        "type": "text",
        "title": "",
        "gridPos": pos,
        "options": {"mode": "markdown", "content": content},
        "transparent": True,
    }


def row(title: str, y: int) -> Panel:
    """A section heading row."""
    return {
        "type": "row",
        "title": title,
        "collapsed": False,
        "gridPos": grid(0, y, 24, 1),
        "panels": [],
    }


ANNOTATIONS = {
    "list": [
        {
            "builtIn": 1,
            "datasource": {"type": "grafana", "uid": "-- Grafana --"},
            "enable": True,
            "hide": True,
            "iconColor": "rgba(0, 211, 255, 1)",
            "name": "Annotations & Alerts",
            "type": "dashboard",
        },
        {
            "name": "Pipeline events",
            "datasource": WAREHOUSE,
            "enable": True,
            "iconColor": "#C4362B",
            "target": query(
                """SELECT occurred_at AS time, title AS text, event_type || ',' || severity AS tags
                FROM ops.pipeline_events WHERE $__timeFilter(occurred_at) ORDER BY occurred_at""",
                datasource=WAREHOUSE,
            ),
        },
    ]
}

# The bucket shown by "at the selected time" panels: the last 5-minute bucket that is
# certainly built when the range ends at that moment (the live dbt job lags ≤ 10 min).
AT_BUCKET_VARIABLE = {
    "name": "at_bucket",
    "label": "Map time (UTC)",
    "type": "query",
    "datasource": WAREHOUSE,
    "query": (
        "SELECT to_char((date_bin('5 minutes', least('${__to:date:iso}'::timestamptz, now()), "
        "timestamptz '2000-01-01') - interval '10 minutes') AT TIME ZONE 'UTC', "
        '\'YYYY-MM-DD"T"HH24:MI:SS"Z"\')'
    ),
    "definition": "last fully built 5-minute bucket at the end of the time range",
    "refresh": 2,
    "hide": 0,
    "includeAll": False,
    "multi": False,
    "sort": 0,
}


def dashboard(
    uid: str,
    title: str,
    description: str,
    panels: list[Panel],
    *,
    refresh: str = "10s",
    time_from: str = "now-6h",
    variables: list[dict[str, Any]] | None = None,
    annotations: bool = True,
) -> dict[str, Any]:
    """Wrap panels in a dashboard model with stable panel ids."""
    for panel_id, panel in enumerate(panels, start=1):
        panel["id"] = panel_id
    return {
        "uid": uid,
        "title": title,
        "description": description,
        "tags": ["dockline"],
        "timezone": "America/New_York",
        "editable": False,
        "graphTooltip": 1,
        "refresh": refresh,
        "time": {"from": time_from, "to": "now"},
        "timepicker": {"refresh_intervals": ["10s", "30s", "1m", "5m", "15m"]},
        "schemaVersion": 41,
        "version": 1,
        "links": [
            {
                "type": "dashboards",
                "tags": ["dockline"],
                "asDropdown": False,
                "includeVars": False,
                "keepTime": True,
                "title": "Dockline",
            }
        ],
        "annotations": ANNOTATIONS if annotations else {"list": []},
        "templating": {"list": variables or []},
        "panels": panels,
    }


# ---------------------------------------------------------------- shared queries

LIVE_STATS = [
    (
        "Empty stations",
        "SELECT MEASURE(empty_stations) FROM fleet_status",
        "none",
        None,
        "In-service, renting stations with 0 bikes right now.",
    ),
    (
        "Full stations",
        "SELECT MEASURE(full_stations) FROM fleet_status",
        "none",
        None,
        "In-service, returning stations with 0 docks right now.",
    ),
    (
        "Bikes available",
        "SELECT MEASURE(bikes_available) FROM fleet_status",
        "none",
        None,
        "Bikes a rider could rent right now, network-wide (includes e-bikes).",
    ),
    ("E-bikes available", "SELECT MEASURE(ebikes_available) FROM fleet_status", "none", None, ""),
    (
        "Docks available",
        "SELECT MEASURE(docks_available) FROM fleet_status",
        "none",
        None,
        "Empty docks a rider could return to right now.",
    ),
    (
        "In service",
        "SELECT MEASURE(stations_in_service) FROM fleet_status",
        "none",
        None,
        "Reporting within 30 minutes, installed, and renting or returning.",
    ),
    (
        "Bikes to move",
        "SELECT MEASURE(rebalance_need_bikes) FROM fleet_status",
        "none",
        None,
        "Bikes to add plus bikes to remove to bring starving and flooding stations to half full.",
    ),
]

FRESHNESS_THRESHOLDS: list[dict[str, Any]] = [
    {"color": "#2E7D4F", "value": None},
    {"color": STATE_COLORS["starving"], "value": 180},
    {"color": "#C4362B", "value": 300},
]


def live_stat_row(y: int) -> list[Panel]:
    """The eight live headline numbers (refresh every 10 s)."""
    panels = [
        stat(title, sql, grid(index * 3, y, 3, 4), unit=unit, description=description)
        for index, (title, sql, unit, _, description) in enumerate(LIVE_STATS)
    ]
    panels.append(
        stat(
            "Data age (s)",
            "SELECT MEASURE(data_freshness_seconds) FROM fleet_status",
            grid(21, y, 3, 4),
            unit="none",
            description="Seconds since the newest station report. Alert fires above 300 s.",
            thresholds=FRESHNESS_THRESHOLDS,
        )
    )
    return panels


HISTORY_BIKES_DOCKS = [
    query(
        """SELECT date_trunc('minute', bucket_start) AS time,
        MEASURE(bikes_available) AS "Bikes available", MEASURE(docks_available) AS "Docks available"
        FROM station_status WHERE $__timeFilter(bucket_start) GROUP BY 1 ORDER BY 1""",
        fmt="time_series",
    )
]

BIKES_DOCKS_OVERRIDES = [
    {
        "matcher": {"id": "byName", "options": "Bikes available"},
        "properties": [{"id": "color", "value": fixed_color(SIGNAL)}],
    },
    {
        "matcher": {"id": "byName", "options": "Docks available"},
        "properties": [{"id": "color", "value": fixed_color(INK_SLATE)}],
    },
]

HISTORY_STATES = [
    query(
        f"""SELECT date_trunc('minute', bucket_start) AS time,
        {", ".join(f'MEASURE({state}_stations) AS "{state}"' for state in STATE_COLORS)}
        FROM station_status WHERE $__timeFilter(bucket_start) GROUP BY 1 ORDER BY 1""",
        fmt="time_series",
    )
]

MAP_AT_BUCKET_SQL = """SELECT stations.station_name AS station, stations.latitude AS latitude,
    stations.longitude AS longitude, station_status.imbalance_state AS state,
    MEASURE(station_status.bikes_available) AS bikes, MEASURE(station_status.docks_available) AS docks
    FROM station_status CROSS JOIN stations
    WHERE station_status.bucket_start = '${at_bucket}'
    GROUP BY 1, 2, 3, 4"""

LIVE_MAP_SQL = """SELECT station_name AS station, latitude, longitude, imbalance_state AS state,
    station_bikes_available AS bikes, station_docks_available AS docks
    FROM fleet_status GROUP BY 1, 2, 3, 4, 5, 6"""


# ---------------------------------------------------------------- dashboards


def live_network_overview() -> dict[str, Any]:
    """Live Network Overview: headline numbers, map, and recent history with rewind."""
    panels: list[Panel] = [
        *live_stat_row(0),
        station_map(
            "Station imbalance at ${at_bucket}",
            MAP_AT_BUCKET_SQL,
            grid(0, 4, 14, 16),
            description=(
                "Each dot is a station at the end of the selected time range (rewind by "
                "changing the time picker). Orange = starving, gray = balanced, blue = "
                "flooding, purple = offline. Hover for the label and counts."
            ),
        ),
        bar_chart(
            "Stations by imbalance state, right now",
            "SELECT imbalance_state AS state, MEASURE(stations) AS stations FROM fleet_status GROUP BY 1 ORDER BY 1",
            grid(14, 4, 10, 8),
            horizontal=True,
            color_by_field="state",
            description="Live. Starving: fill ≤ 20% or no bikes. Flooding: fill ≥ 80% or no docks.",
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "state"},
                    "properties": [{"id": "mappings", "value": state_value_mappings()}],
                }
            ],
        ),
        timeseries(
            "Availability rate by borough",
            [
                query(
                    """SELECT date_trunc('minute', station_status.bucket_start) AS time,
                    stations.borough AS metric, MEASURE(station_status.availability_rate) AS value
                    FROM station_status CROSS JOIN stations
                    WHERE $__timeFilter(station_status.bucket_start)
                    GROUP BY 1, 2 ORDER BY 1""",
                    fmt="time_series",
                )
            ],
            grid(14, 12, 10, 8),
            unit="percentunit",
            max_value=1,
            description="Share of in-service station-minutes with at least one bike and one dock.",
        ),
        timeseries(
            "Bikes and docks available",
            HISTORY_BIKES_DOCKS,
            grid(0, 20, 12, 8),
            description="Network totals every 5 minutes.",
            overrides=BIKES_DOCKS_OVERRIDES,
        ),
        timeseries(
            "Stations by imbalance state",
            HISTORY_STATES,
            grid(12, 20, 12, 8),
            stacked=True,
            overrides=state_series_overrides(),
            description="Every station is in exactly one state in each 5-minute bucket.",
        ),
        timeseries(
            "Empty and full stations",
            [
                query(
                    """SELECT date_trunc('minute', bucket_start) AS time,
                    MEASURE(empty_stations) AS "No bikes", MEASURE(full_stations) AS "No docks"
                    FROM station_status WHERE $__timeFilter(bucket_start) GROUP BY 1 ORDER BY 1""",
                    fmt="time_series",
                )
            ],
            grid(0, 28, 12, 8),
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "No bikes"},
                    "properties": [{"id": "color", "value": fixed_color(STATE_COLORS["starving"])}],
                },
                {
                    "matcher": {"id": "byName", "options": "No docks"},
                    "properties": [{"id": "color", "value": fixed_color(STATE_COLORS["flooding"])}],
                },
            ],
        ),
        timeseries(
            "Net flow (bikes per 5 minutes)",
            [
                query(
                    """SELECT date_trunc('minute', bucket_start) AS time, MEASURE(net_flow) AS "Net flow"
                    FROM station_status WHERE $__timeFilter(bucket_start) GROUP BY 1 ORDER BY 1""",
                    fmt="time_series",
                )
            ],
            grid(12, 28, 12, 8),
            description="Change in bikes on hand across the network. Trucks move bikes too: this is not trips.",
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "Net flow"},
                    "properties": [{"id": "color", "value": fixed_color(SIGNAL)}],
                },
            ],
        ),
    ]
    return dashboard(
        "dockline-live",
        "Live Network Overview",
        "Live state of every Citi Bike station. Headline numbers are live; the map and "
        "charts follow the time picker for rewind.",
        panels,
        variables=[AT_BUCKET_VARIABLE],
    )


def station_drilldown() -> dict[str, Any]:
    """Station Drilldown: one station's live state, history, and chronic verdict."""
    station_variable = {
        "name": "station",
        "label": "Station",
        "type": "query",
        "datasource": CUBE,
        "query": "SELECT station_id AS __value, station_name AS __text FROM fleet_status GROUP BY 1, 2 ORDER BY 2",
        "definition": "stations listed in the feed",
        "refresh": 1,
        "hide": 0,
        "includeAll": False,
        "multi": False,
        "sort": 1,
    }
    live_where = "WHERE station_id = '${station}'"
    panels: list[Panel] = [
        stat(
            "Bikes available",
            f"SELECT MEASURE(bikes_available) FROM fleet_status {live_where}",
            grid(0, 0, 4, 4),
        ),
        stat(
            "E-bikes available",
            f"SELECT MEASURE(ebikes_available) FROM fleet_status {live_where}",
            grid(4, 0, 4, 4),
        ),
        stat(
            "Docks available",
            f"SELECT MEASURE(docks_available) FROM fleet_status {live_where}",
            grid(8, 0, 4, 4),
        ),
        stat(
            "Fill ratio",
            f"SELECT MEASURE(fill_ratio) FROM fleet_status {live_where}",
            grid(12, 0, 4, 4),
            unit="percentunit",
            decimals=0,
        ),
        {
            **stat(
                "Imbalance state",
                f"SELECT imbalance_state AS state FROM fleet_status {live_where} GROUP BY 1",
                grid(16, 0, 4, 4),
            ),
            "fieldConfig": {
                "defaults": {
                    "mappings": state_value_mappings(),
                    "color": {"mode": "fixed", "fixedColor": INK_SLATE},
                },
                "overrides": [],
            },
            "options": {
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "/^state$/", "values": False},
                "colorMode": "background",
                "graphMode": "none",
                "textMode": "value",
            },
        },
        stat(
            "Minutes since last report",
            f"SELECT minutes_since_report FROM fleet_status {live_where} GROUP BY 1",
            grid(20, 0, 4, 4),
            decimals=1,
            thresholds=[
                {"color": "#2E7D4F", "value": None},
                {"color": STATE_COLORS["starving"], "value": 15},
                {"color": "#C4362B", "value": 30},
            ],
        ),
        timeseries(
            "Bikes, e-bikes, and docks",
            [
                query(
                    """SELECT date_trunc('minute', bucket_start) AS time,
                    MEASURE(bikes_available) AS "Bikes", MEASURE(ebikes_available) AS "E-bikes",
                    MEASURE(docks_available) AS "Docks"
                    FROM station_status
                    WHERE station_id = '${station}' AND $__timeFilter(bucket_start)
                    GROUP BY 1 ORDER BY 1""",
                    fmt="time_series",
                )
            ],
            grid(0, 4, 16, 9),
            description="State at the end of each 5-minute bucket. Gaps mean the station was offline.",
        ),
        table(
            "Chronic verdict (weekday peaks, last 14 days)",
            """SELECT chronic_status AS "Verdict", peak_hours_observed AS "Peak hours observed",
            peak_empty_share AS "Empty share", peak_full_share AS "Full share"
            FROM chronic_stations WHERE station_id = '${station}' GROUP BY 1, 2, 3, 4""",
            grid(16, 4, 8, 9),
            overrides=[
                {
                    "matcher": {"id": "byRegexp", "options": ".*share"},
                    "properties": [{"id": "unit", "value": "percentunit"}],
                },
            ],
        ),
        timeseries(
            "Fill ratio (dashed line = 50% target)",
            [
                query(
                    """SELECT date_trunc('minute', bucket_start) AS time, MEASURE(fill_ratio) AS "Fill ratio"
                    FROM station_status
                    WHERE station_id = '${station}' AND $__timeFilter(bucket_start)
                    GROUP BY 1 ORDER BY 1""",
                    fmt="time_series",
                )
            ],
            grid(0, 13, 12, 8),
            unit="percentunit",
            min_value=0,
            max_value=1,
            target_line=0.5,
        ),
        bar_chart(
            "Empty and full minutes by hour of day",
            """SELECT CAST(hour_of_day AS TEXT) AS hour, MEASURE(empty_station_minutes) AS "Empty minutes",
            MEASURE(full_station_minutes) AS "Full minutes"
            FROM station_hourly
            WHERE station_id = '${station}' AND $__timeFilter(hour_start)
            GROUP BY hour_of_day ORDER BY hour_of_day""",
            grid(12, 13, 12, 8),
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "Empty minutes"},
                    "properties": [{"id": "color", "value": fixed_color(STATE_COLORS["starving"])}],
                },
                {
                    "matcher": {"id": "byName", "options": "Full minutes"},
                    "properties": [{"id": "color", "value": fixed_color(STATE_COLORS["flooding"])}],
                },
            ],
            description="Local hour of day.",
        ),
    ]
    return dashboard(
        "dockline-station",
        "Station Drilldown",
        "One station: live state, 5-minute history, hourly pattern, and chronic verdict.",
        panels,
        refresh="30s",
        time_from="now-24h",
        variables=[station_variable],
    )


def rebalancing_board() -> dict[str, Any]:
    """Rebalancing Board: live list of stations to visit, ranked."""
    panels: list[Panel] = [
        stat(
            "Starving stations",
            "SELECT MEASURE(starving_stations) FROM fleet_status",
            grid(0, 0, 6, 4),
            color=STATE_COLORS["starving"],
            description="Fill ≤ 20% or no bikes.",
        ),
        stat(
            "Bikes to add",
            "SELECT MEASURE(rebalance_need_bikes) FROM fleet_status WHERE imbalance_state = 'starving'",
            grid(6, 0, 6, 4),
            color=STATE_COLORS["starving"],
        ),
        stat(
            "Flooding stations",
            "SELECT MEASURE(flooding_stations) FROM fleet_status",
            grid(12, 0, 6, 4),
            color=STATE_COLORS["flooding"],
            description="Fill ≥ 80% or no docks.",
        ),
        stat(
            "Bikes to remove",
            "SELECT MEASURE(rebalance_need_bikes) FROM fleet_status WHERE imbalance_state = 'flooding'",
            grid(18, 0, 6, 4),
            color=STATE_COLORS["flooding"],
        ),
        table(
            "Visit next (top 40 by priority)",
            """SELECT priority_rank AS "Rank", station_name AS "Station", borough AS "Borough",
            neighborhood AS "Neighborhood", recommended_action AS "Action", bikes_to_move AS "Bikes",
            station_bikes_available AS "Bikes now", station_docks_available AS "Docks now",
            station_fill_ratio AS "Fill", typical_hourly_turnover AS "Typical turnover / h",
            imbalance_state AS "State"
            FROM fleet_status WHERE priority_rank IS NOT NULL AND priority_rank <= 40
            GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 ORDER BY 1""",
            grid(0, 4, 14, 20),
            description=(
                "Priority = bikes to move × (1 + ln(1 + typical turnover at this hour)). "
                "Bikes to move brings the station to half full."
            ),
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "Fill"},
                    "properties": [
                        {"id": "unit", "value": "percentunit"},
                        {"id": "decimals", "value": 0},
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "Typical turnover / h"},
                    "properties": [{"id": "decimals", "value": 1}],
                },
                {
                    "matcher": {"id": "byName", "options": "State"},
                    "properties": [
                        {"id": "mappings", "value": state_value_mappings()},
                        {"id": "custom.cellOptions", "value": {"type": "color-text"}},
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "Rank"},
                    "properties": [{"id": "custom.width", "value": 60}],
                },
            ],
        ),
        station_map(
            "Stations that need a visit",
            """SELECT station_name AS station, latitude, longitude, imbalance_state AS state,
            recommended_action AS action, bikes_to_move AS bikes_to_move
            FROM fleet_status WHERE priority_rank IS NOT NULL GROUP BY 1, 2, 3, 4, 5, 6""",
            grid(14, 4, 10, 12),
            description="Orange = add bikes (starving). Blue = remove bikes (flooding).",
        ),
        bar_chart(
            "Bikes to move by borough",
            """SELECT borough, imbalance_state AS state, MEASURE(rebalance_need_bikes) AS bikes
            FROM fleet_status WHERE imbalance_state IN ('starving', 'flooding')
            GROUP BY 1, 2 ORDER BY 1""",
            grid(14, 16, 10, 8),
            stacked=True,
            description="Orange = bikes to add, blue = bikes to remove.",
        ),
    ]
    # Pivot borough × state into one column per state for the stacked bar chart.
    panels[-1]["transformations"] = [
        {
            "id": "groupingToMatrix",
            "options": {"columnField": "state", "rowField": "borough", "valueField": "bikes"},
        },
    ]
    panels[-1]["fieldConfig"]["overrides"] = state_series_overrides()
    return dashboard(
        "dockline-rebalancing",
        "Rebalancing Board",
        "Live list of starving and flooding stations, ranked by bikes to move weighted by demand.",
        panels,
    )


def daily_review() -> dict[str, Any]:
    """Daily Review: availability by day, borough, hour, and weather."""
    range_daily = "WHERE $__timeFilter(service_date)"
    panels: list[Panel] = [
        stat(
            "Availability rate",
            f"SELECT MEASURE(availability_rate) FROM daily_kpis {range_daily}",
            grid(0, 0, 4, 4),
            unit="percentunit",
            decimals=1,
            description="Share of in-service station-minutes with at least one bike and one dock.",
        ),
        stat(
            "Empty share",
            f"SELECT MEASURE(empty_share) FROM daily_kpis {range_daily}",
            grid(4, 0, 4, 4),
            unit="percentunit",
            decimals=1,
            color=STATE_COLORS["starving"],
        ),
        stat(
            "Full share",
            f"SELECT MEASURE(full_share) FROM daily_kpis {range_daily}",
            grid(8, 0, 4, 4),
            unit="percentunit",
            decimals=1,
            color=STATE_COLORS["flooding"],
        ),
        stat(
            "Bikes added",
            f"SELECT MEASURE(bikes_added) FROM daily_kpis {range_daily}",
            grid(12, 0, 4, 4),
        ),
        stat(
            "Bikes removed",
            f"SELECT MEASURE(bikes_removed) FROM daily_kpis {range_daily}",
            grid(16, 0, 4, 4),
        ),
        stat(
            "Chronic problem stations",
            "SELECT MEASURE(chronic_problem_stations) FROM chronic_stations",
            grid(20, 0, 4, 4),
            color=STATE_COLORS["starving"],
            description="Empty or full > 25% of weekday-peak minutes over the last 14 days (needs ≥ 10 peak hours).",
        ),
        timeseries(
            "Availability rate by day and borough",
            [
                query(
                    """SELECT date_trunc('day', service_date) AS time, borough AS metric,
                    MEASURE(availability_rate) AS value
                    FROM daily_kpis WHERE $__timeFilter(service_date) GROUP BY 1, 2 ORDER BY 1""",
                    fmt="time_series",
                )
            ],
            grid(0, 4, 14, 9),
            unit="percentunit",
            max_value=1,
            points=True,
        ),
        table(
            "Borough summary for the selected range",
            """SELECT borough AS "Borough", MEASURE(availability_rate) AS "Availability",
            MEASURE(empty_share) AS "Empty share", MEASURE(full_share) AS "Full share",
            MEASURE(bikes_added) AS "Bikes added", MEASURE(bikes_removed) AS "Bikes removed"
            FROM daily_kpis WHERE $__timeFilter(service_date) GROUP BY 1 ORDER BY 2""",
            grid(14, 4, 10, 9),
            overrides=[
                {
                    "matcher": {"id": "byRegexp", "options": "Availability|.*share"},
                    "properties": [
                        {"id": "unit", "value": "percentunit"},
                        {"id": "decimals", "value": 1},
                    ],
                },
            ],
        ),
        bar_chart(
            "Empty and full share by hour of day (local)",
            """SELECT CAST(hour_of_day AS TEXT) AS hour, MEASURE(empty_share) AS "Empty share",
            MEASURE(full_share) AS "Full share"
            FROM station_hourly WHERE $__timeFilter(hour_start)
            GROUP BY hour_of_day ORDER BY hour_of_day""",
            grid(0, 13, 14, 9),
            unit="percentunit",
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "Empty share"},
                    "properties": [{"id": "color", "value": fixed_color(STATE_COLORS["starving"])}],
                },
                {
                    "matcher": {"id": "byName", "options": "Full share"},
                    "properties": [{"id": "color", "value": fixed_color(STATE_COLORS["flooding"])}],
                },
            ],
        ),
        bar_chart(
            "Availability by weather condition",
            """SELECT weather.weather_condition AS condition,
            MEASURE(station_hourly.availability_rate) AS "Availability"
            FROM station_hourly CROSS JOIN weather
            WHERE $__timeFilter(station_hourly.hour_start) GROUP BY 1 ORDER BY 1""",
            grid(14, 13, 10, 9),
            unit="percentunit",
            horizontal=True,
            max_value=1,
        ),
        bar_chart(
            "Availability by temperature band",
            """SELECT weather.temperature_band AS band,
            MEASURE(station_hourly.availability_rate) AS "Availability"
            FROM station_hourly CROSS JOIN weather
            WHERE $__timeFilter(station_hourly.hour_start)
            GROUP BY weather.temperature_band, weather.temperature_band_order
            ORDER BY weather.temperature_band_order""",
            grid(0, 22, 12, 8),
            unit="percentunit",
            max_value=1,
        ),
        bar_chart(
            "Weekday vs weekend availability",
            """SELECT dates.day_type AS day_type,
            MEASURE(station_hourly.availability_rate) AS "Availability"
            FROM station_hourly CROSS JOIN dates
            WHERE $__timeFilter(station_hourly.hour_start) GROUP BY 1 ORDER BY 1""",
            grid(12, 22, 12, 8),
            unit="percentunit",
            max_value=1,
        ),
    ]
    return dashboard(
        "dockline-daily",
        "Daily Review",
        "Availability, empty and full time, and their drivers over days (borough, hour, weather).",
        panels,
        refresh="5m",
        time_from="now-14d",
    )


def public_live() -> dict[str, Any]:
    """Compact live dashboard for public embedding (public dashboards allow no variables)."""
    panels: list[Panel] = [
        *live_stat_row(0),
        station_map(
            "Stations right now",
            LIVE_MAP_SQL,
            grid(0, 4, 14, 14),
        ),
        timeseries(
            "Bikes and docks available",
            HISTORY_BIKES_DOCKS,
            grid(14, 4, 10, 7),
            overrides=BIKES_DOCKS_OVERRIDES,
        ),
        timeseries(
            "Stations by imbalance state",
            HISTORY_STATES,
            grid(14, 11, 10, 7),
            stacked=True,
            overrides=state_series_overrides(),
        ),
        text(
            "Independent project. Not affiliated with Citi Bike or Lyft. Uses the public GBFS feed.",
            grid(0, 18, 24, 2),
        ),
    ]
    return dashboard(
        "dockline-public-live",
        "Dockline Live (public)",
        "Public, embeddable live view of the Citi Bike network.",
        panels,
        annotations=False,
    )


DASHBOARDS = {
    "live-network-overview.json": live_network_overview,
    "station-drilldown.json": station_drilldown,
    "rebalancing-board.json": rebalancing_board,
    "daily-review.json": daily_review,
    "public-live.json": public_live,
}


def render_all() -> dict[str, str]:
    """Return file name -> JSON text for every dashboard."""
    return {
        name: json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
        for name, build in DASHBOARDS.items()
    }


def main() -> None:
    """Write every dashboard to grafana/dashboards/."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    for name, content in render_all().items():
        (OUTPUT_DIR / name).write_text(content)
        print(f"wrote {OUTPUT_DIR / name}")


if __name__ == "__main__":
    main()
