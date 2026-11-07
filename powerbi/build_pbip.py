"""Generate the Dockline Power BI project (PBIP: TMDL semantic model + PBIR report).

Everything under powerbi/Dockline.* and powerbi/theme/ is generated from the spec in
this file. Edit here, run ``make powerbi``, and commit the output. A test fails if the
committed files differ from what this script produces.

Design rules (CLAUDE.md, Phase 4):
* DirectQuery to the ``bi`` schema through parameters DbHost / DbPort / DbName.
* DAX measure names are exactly the Cube measure names, and each fact table is named
  after its cube (fleet_status, station_hourly, chronic_stations), so the two semantic
  layers can be compared one-to-one (tests/test_powerbi.py).
* Row-level security by borough on the Borough table.
* Dockline theme and state colors; auto page refresh on Live Operations.

Usage: ``python3 powerbi/build_pbip.py`` (stdlib only).
"""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROJECT_NAME = "Dockline"
MODEL_DIR = ROOT / f"{PROJECT_NAME}.SemanticModel"
REPORT_DIR = ROOT / f"{PROJECT_NAME}.Report"
THEME_PATH = ROOT / "theme" / "dockline.json"

# Stable identifiers: lineage tags and names are UUID5s of a readable key, so the
# generated files only change when the spec changes.
NAMESPACE = uuid.UUID("6f1d3c52-6a8e-4bd4-9a47-2a2f1f6c0d11")

SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric"
SCHEMAS = {
    "pbip": f"{SCHEMA_BASE}/pbip/pbipProperties/1.0.0/schema.json",
    "pbir": f"{SCHEMA_BASE}/item/report/definitionProperties/2.0.0/schema.json",
    "pbism": f"{SCHEMA_BASE}/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "platform": f"{SCHEMA_BASE}/gitIntegration/platformProperties/2.0.0/schema.json",
    "version": f"{SCHEMA_BASE}/item/report/definition/versionMetadata/1.0.0/schema.json",
    "report": f"{SCHEMA_BASE}/item/report/definition/report/3.3.0/schema.json",
    "pages": f"{SCHEMA_BASE}/item/report/definition/pagesMetadata/1.1.0/schema.json",
    "page": f"{SCHEMA_BASE}/item/report/definition/page/2.1.0/schema.json",
    "visual": f"{SCHEMA_BASE}/item/report/definition/visualContainer/2.13.0/schema.json",
}

# Dockline design system.
INK = "#13202F"
SLATE = "#4A5A6E"
PAPER = "#F6F7F9"
SURFACE = "#FFFFFF"
LINE = "#D9DEE5"
SIGNAL = "#1B5FD1"
STATE_COLORS = {
    "starving": "#E0701F",
    "balanced": "#A9B3C1",
    "flooding": "#2357C6",
    "offline": "#7A6F9B",
}
BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island", "Jersey City", "Hoboken"]


def stable_id(*parts: str) -> str:
    """Deterministic UUID for a lineage tag or object name."""
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


def short_id(*parts: str) -> str:
    """Deterministic 20-hex-character name for PBIR pages and visuals."""
    return uuid.uuid5(NAMESPACE, "/".join(parts)).hex[:20]


# ====================================================================== model spec


@dataclass
class Column:
    """A column of a DirectQuery table (name = source column in the bi view)."""

    name: str
    data_type: str  # string | int64 | double | boolean | dateTime
    description: str = ""
    hidden: bool = False
    format_string: str | None = None
    sort_by: str | None = None
    is_key: bool = False
    summarize_by: str = "none"
    data_category: str | None = None


@dataclass
class Measure:
    """A DAX measure. ``name`` must equal the Cube measure name in the same cube."""

    name: str
    expression: str
    format_string: str
    folder: str
    description: str
    hidden: bool = False


@dataclass
class Table:
    """A table in the semantic model, backed by one view in the ``bi`` schema."""

    name: str
    view: str
    description: str
    columns: list[Column]
    measures: list[Measure] = field(default_factory=list)
    hidden: bool = False
    data_category: str | None = None
    cube: str | None = None  # the Cube cube whose measures this table mirrors


def col(name: str, data_type: str, description: str = "", **kwargs: Any) -> Column:
    """Shorthand for a column."""
    return Column(name, data_type, description, **kwargs)


def key(name: str, data_type: str = "string", description: str = "Join key.") -> Column:
    """A hidden key column."""
    return Column(name, data_type, description, hidden=True)


IN_SERVICE = "fleet_status[is_in_service] = TRUE()"

TABLES: list[Table] = [
    Table(
        name="fleet_status",
        view="fleet_status",
        cube="fleet_status",
        description="Live state of every listed station. Mirrors the Cube cube fleet_status.",
        columns=[
            key("station_key"),
            col("station_bikes_available", "int64", "Bikes at this station now.", hidden=True),
            col("station_ebikes_available", "int64", "E-bikes at this station now.", hidden=True),
            col("station_docks_available", "int64", "Free docks at this station now.", hidden=True),
            col("station_bikes_disabled", "int64", hidden=True),
            col("station_docks_disabled", "int64", hidden=True),
            col(
                "is_in_service",
                "boolean",
                "Reported within 30 minutes, installed, renting or returning.",
            ),
            col("station_fill_ratio", "double", "Fill ratio of this station.", format_string="0%"),
            col("station_imbalance_index", "double", format_string="0.00"),
            col("imbalance_state", "string", "starving, balanced, flooding, or offline."),
            col(
                "station_rebalance_need_bikes",
                "int64",
                "Bikes to add (+) or remove (−) to reach half full.",
            ),
            col("recommended_action", "string", "Add bikes, Remove bikes, or No action."),
            col("bikes_to_move", "int64", "Bikes to move at this station (0 when balanced)."),
            col("priority_score", "double", format_string="0.0"),
            col("priority_rank", "int64", "1 = visit first. Blank when no action is needed."),
            col(
                "typical_hourly_turnover",
                "double",
                "Typical bikes in + out at this hour.",
                format_string="0.0",
            ),
            col(
                "minutes_empty",
                "double",
                "Minutes since the station last had a bike.",
                format_string="0",
            ),
            col("is_high_traffic", "boolean", "Busiest 10% of stations at this hour."),
            col("minutes_since_report", "double", format_string="0.0"),
            col(
                "last_reported_at_utc", "dateTime", hidden=True, format_string="yyyy-mm-dd hh:nn:ss"
            ),
            col(
                "last_reported_at_local",
                "dateTime",
                "Last report, New York time.",
                format_string="yyyy-mm-dd hh:nn:ss",
            ),
            col("computed_at_utc", "dateTime", hidden=True, format_string="yyyy-mm-dd hh:nn:ss"),
        ],
        measures=[
            Measure(
                "bikes_available",
                f"CALCULATE(SUM(fleet_status[station_bikes_available]), {IN_SERVICE})",
                "#,0",
                "Live\\Availability",
                "Bikes a rider could rent right now (in-service stations; includes e-bikes).",
            ),
            Measure(
                "ebikes_available",
                f"CALCULATE(SUM(fleet_status[station_ebikes_available]), {IN_SERVICE})",
                "#,0",
                "Live\\Availability",
                "E-bikes a rider could rent right now.",
            ),
            Measure(
                "docks_available",
                f"CALCULATE(SUM(fleet_status[station_docks_available]), {IN_SERVICE})",
                "#,0",
                "Live\\Availability",
                "Empty docks a rider could return to right now.",
            ),
            Measure(
                "usable_slots",
                "[bikes_available] + [docks_available]",
                "#,0",
                "Live\\Availability",
                "Bikes plus free docks at in-service stations (helper).",
                hidden=True,
            ),
            Measure(
                "fill_ratio",
                "DIVIDE([bikes_available], [usable_slots])",
                "0.0%",
                "Live\\Availability",
                "bikes_available / (bikes_available + docks_available).",
            ),
            Measure(
                "imbalance_index",
                "[fill_ratio] - 0.5",
                "0.000",
                "Live\\Availability",
                "fill_ratio minus the 0.5 target. Negative = starving, positive = flooding.",
            ),
            Measure(
                "stations",
                "COUNTROWS(fleet_status)",
                "#,0",
                "Live\\Station counts",
                "Stations listed in the feed.",
            ),
            Measure(
                "stations_in_service",
                f"CALCULATE(COUNTROWS(fleet_status), {IN_SERVICE})",
                "#,0",
                "Live\\Station counts",
                "Stations reporting, installed, and renting or returning.",
            ),
            Measure(
                "empty_stations",
                f"CALCULATE(COUNTROWS(fleet_status), {IN_SERVICE}, fleet_status[station_bikes_available] = 0)",
                "#,0",
                "Live\\Station counts",
                "In-service stations with no bike to rent right now.",
            ),
            Measure(
                "full_stations",
                f"CALCULATE(COUNTROWS(fleet_status), {IN_SERVICE}, fleet_status[station_docks_available] = 0)",
                "#,0",
                "Live\\Station counts",
                "In-service stations with no free dock right now.",
            ),
            *[
                Measure(
                    f"{state}_stations",
                    f'CALCULATE(COUNTROWS(fleet_status), fleet_status[imbalance_state] = "{state}")',
                    "#,0",
                    "Live\\Station counts",
                    f"Stations in the {state} state right now.",
                )
                for state in STATE_COLORS
            ],
            Measure(
                "rebalance_need_bikes",
                "SUM(fleet_status[bikes_to_move])",
                "#,0",
                "Live\\Rebalancing",
                "Bikes to add plus bikes to remove to bring starving and flooding stations to half full.",
            ),
            Measure(
                "longest_empty_minutes",
                "MAX(fleet_status[minutes_empty])",
                "0",
                "Live\\Rebalancing",
                "Longest current empty spell among the stations in context (minutes).",
            ),
            Measure(
                "data_freshness_seconds",
                "DATEDIFF(MAX(fleet_status[last_reported_at_utc]), UTCNOW(), SECOND)",
                "#,0",
                "Live\\Data quality",
                "Seconds since the newest station report (now − latest last_reported).",
            ),
        ],
    ),
    Table(
        name="station_hourly",
        view="station_hourly",
        cube="station_hourly",
        description="Station activity per clock hour. Mirrors the Cube cube station_hourly.",
        columns=[
            key("station_key"),
            key("date_key", "int64"),
            key("hour_of_day", "int64"),
            key("weather_hour_key", "int64"),
            col(
                "hour_start_local",
                "dateTime",
                "Hour start, New York time.",
                format_string="yyyy-mm-dd hh:nn",
            ),
            col("is_peak_period", "boolean", "Weekday 7–10 or 16–20 local time."),
            col("observed_minutes", "int64", hidden=True),
            col("in_service_minutes", "int64", hidden=True),
            col("empty_minutes", "int64", hidden=True),
            col("full_minutes", "int64", hidden=True),
            col("available_minutes", "int64", hidden=True),
            col("offline_minutes", "int64", hidden=True),
            col("avg_station_bikes", "double", hidden=True),
            col("avg_station_docks", "double", hidden=True),
            col("avg_station_fill_ratio", "double", hidden=True),
            col("net_flow_bikes", "int64", hidden=True),
            col("added_bikes", "int64", hidden=True),
            col("removed_bikes", "int64", hidden=True),
            col("imbalance_state_end", "string", "State at the end of the hour."),
        ],
        measures=[
            Measure(
                "in_service_station_minutes",
                "SUM(station_hourly[in_service_minutes])",
                "#,0",
                "History\\Minutes",
                "Station-minutes in service.",
            ),
            Measure(
                "empty_station_minutes",
                "SUM(station_hourly[empty_minutes])",
                "#,0",
                "History\\Minutes",
                "Minutes stations had no bike to rent while renting.",
            ),
            Measure(
                "full_station_minutes",
                "SUM(station_hourly[full_minutes])",
                "#,0",
                "History\\Minutes",
                "Minutes stations had no free dock while returning.",
            ),
            Measure(
                "available_station_minutes",
                "SUM(station_hourly[available_minutes])",
                "#,0",
                "History\\Minutes",
                "In-service minutes with at least one bike and one dock.",
            ),
            Measure(
                "offline_station_minutes",
                "SUM(station_hourly[offline_minutes])",
                "#,0",
                "History\\Minutes",
                "Station-minutes not in service.",
            ),
            Measure(
                "availability_rate",
                "DIVIDE([available_station_minutes], [in_service_station_minutes])",
                "0.0%",
                "History\\Rates",
                "Share of in-service station-minutes with at least one bike and one dock.",
            ),
            Measure(
                "empty_share",
                "DIVIDE([empty_station_minutes], [in_service_station_minutes])",
                "0.0%",
                "History\\Rates",
                "Share of in-service station-minutes with no bike.",
            ),
            Measure(
                "full_share",
                "DIVIDE([full_station_minutes], [in_service_station_minutes])",
                "0.0%",
                "History\\Rates",
                "Share of in-service station-minutes with no free dock.",
            ),
            Measure(
                "net_flow",
                "SUM(station_hourly[net_flow_bikes])",
                "#,0",
                "History\\Flow",
                "Change in bikes on hand. Includes rebalancing trucks; not trips.",
            ),
            Measure(
                "bikes_added",
                "SUM(station_hourly[added_bikes])",
                "#,0",
                "History\\Flow",
                "Sum of positive 5-minute changes.",
            ),
            Measure(
                "bikes_removed",
                "SUM(station_hourly[removed_bikes])",
                "#,0",
                "History\\Flow",
                "Sum of negative 5-minute changes (as a positive number).",
            ),
            Measure(
                "station_hours",
                "COUNTROWS(station_hourly)",
                "#,0",
                "History\\Minutes",
                "Station-hours observed.",
            ),
        ],
    ),
    Table(
        name="chronic_stations",
        view="chronic_stations",
        cube="chronic_stations",
        description="Weekday-peak verdict per station over the last 14 days. Mirrors chronic_stations.",
        columns=[
            key("station_key"),
            col(
                "chronic_status",
                "string",
                "insufficient_data, ok, chronic_empty, chronic_full, chronic_empty_and_full.",
            ),
            col("chronic_problem_station", "boolean"),
            col("peak_hours_observed", "int64"),
            col("peak_in_service_minutes", "double", hidden=True),
            col("peak_empty_minutes", "double", hidden=True),
            col("peak_full_minutes", "double", hidden=True),
            col("peak_empty_share", "double", format_string="0.0%"),
            col("peak_full_share", "double", format_string="0.0%"),
            col("lookback_days", "int64", hidden=True),
        ],
        measures=[
            Measure(
                "chronic_problem_stations",
                "CALCULATE(COUNTROWS(chronic_stations), chronic_stations[chronic_problem_station] = TRUE())",
                "#,0",
                "Chronic",
                "Stations empty or full > 25% of in-service weekday-peak minutes (≥ 10 peak hours observed).",
            ),
            Measure(
                "stations_rated",
                'CALCULATE(COUNTROWS(chronic_stations), chronic_stations[chronic_status] <> "insufficient_data")',
                "#,0",
                "Chronic",
                "Stations with enough peak data for a verdict.",
            ),
        ],
    ),
    Table(
        name="Station",
        view="station",
        description="Stations (one row per version; facts join to the version valid at the time).",
        columns=[
            key("station_key"),
            col("station_id", "string", "GBFS station id.", hidden=True),
            col("station_name", "string", "Station name."),
            col("short_name", "string"),
            col("borough", "string", hidden=True),
            col("neighborhood", "string", "NYC 2020 neighborhood (NTA)."),
            col("capacity", "int64", "Docks at the station."),
            col("latitude", "double", data_category="Latitude", format_string="0.00000"),
            col("longitude", "double", data_category="Longitude", format_string="0.00000"),
            col("has_ebike_charging", "boolean"),
            col("is_current", "boolean", "Current version of the station."),
            col("valid_from_local", "dateTime", hidden=True),
            col("valid_to_local", "dateTime", hidden=True),
        ],
    ),
    Table(
        name="Borough",
        view="borough",
        description="Boroughs. Row-level security roles filter this table.",
        columns=[
            col(
                "borough", "string", "Borough (or Jersey City / Hoboken).", sort_by="borough_order"
            ),
            col("city", "string", "New York City or New Jersey."),
            col("borough_order", "int64", hidden=True),
        ],
    ),
    Table(
        name="Date",
        view="date",
        description="Calendar (New York local dates). Marked as the date table.",
        data_category="Time",
        columns=[
            key("date_key", "int64"),
            col("calendar_date", "dateTime", "Date.", is_key=True, format_string="yyyy-mm-dd"),
            col("year", "int64"),
            col("quarter", "int64"),
            col("month", "int64", hidden=True),
            col("month_name", "string", sort_by="month"),
            col("month_short_name", "string", sort_by="month"),
            col("day_of_month", "int64"),
            col("day_of_week", "int64", hidden=True),
            col("day_name", "string", sort_by="day_of_week"),
            col("day_short_name", "string", sort_by="day_of_week"),
            col("is_weekend", "boolean"),
            col("day_type", "string", "Weekday or Weekend."),
            col("week_start_date", "dateTime", format_string="yyyy-mm-dd"),
            col("month_start_date", "dateTime", format_string="yyyy-mm-dd"),
        ],
    ),
    Table(
        name="Hour",
        view="hour",
        description="Hour of day (New York local time).",
        columns=[
            col("hour_of_day", "int64", "0–23."),
            col("hour_label", "string", "12 AM … 11 PM.", sort_by="hour_of_day"),
            col("day_part", "string", sort_by="day_part_order"),
            col("day_part_order", "int64", hidden=True),
            col("is_peak_hour", "boolean", "Commute peak hour (applies on weekdays)."),
        ],
    ),
    Table(
        name="Weather",
        view="weather",
        cube="weather",
        description="Hourly weather for central NYC (Open-Meteo).",
        columns=[
            key("weather_hour_key", "int64"),
            col("weather_hour_local", "dateTime", format_string="yyyy-mm-dd hh:nn"),
            col("temperature_c", "double", hidden=True),
            col("temperature_f", "double", hidden=True),
            col("apparent_temperature_c", "double", hidden=True),
            col("precipitation_mm", "double", hidden=True),
            col("snowfall_cm", "double", hidden=True),
            col(
                "weather_condition",
                "string",
                "Clear, Cloudy, Fog, Drizzle, Rain, Snow, Thunderstorm.",
            ),
            col("weather_description", "string"),
            col("temperature_band", "string", sort_by="temperature_band_order"),
            col("temperature_band_order", "int64", hidden=True),
            col("is_precipitating", "boolean"),
            col("wind_speed_kmh", "double", hidden=True),
            col("is_forecast", "boolean", hidden=True),
        ],
        measures=[
            Measure(
                "avg_temperature_c",
                "AVERAGE(Weather[temperature_c])",
                "0.0",
                "Weather",
                "Average temperature (°C).",
            ),
            Measure(
                "total_precipitation_mm",
                "SUM(Weather[precipitation_mm])",
                "0.0",
                "Weather",
                "Precipitation (mm).",
            ),
        ],
    ),
]

# (from table, from column, to table, to column): many-to-one, single direction.
RELATIONSHIPS = [
    ("fleet_status", "station_key", "Station", "station_key"),
    ("station_hourly", "station_key", "Station", "station_key"),
    ("chronic_stations", "station_key", "Station", "station_key"),
    ("Station", "borough", "Borough", "borough"),
    ("station_hourly", "date_key", "Date", "date_key"),
    ("station_hourly", "hour_of_day", "Hour", "hour_of_day"),
    ("station_hourly", "weather_hour_key", "Weather", "weather_hour_key"),
]

PARAMETERS = [
    (
        "DbHost",
        '"10.211.55.2"',
        "Text",
        "Warehouse host as seen from the Windows VM (Parallels default).",
    ),
    ("DbPort", "5433", "Number", "Published Postgres port (POSTGRES_PORT)."),
    ("DbName", '"dockline"', "Text", "Warehouse database (POSTGRES_DB)."),
]


# ====================================================================== TMDL writers


def tmdl_name(name: str) -> str:
    """Quote a TMDL object name when it is not a plain identifier."""
    if name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def dax_table(name: str) -> str:
    """Table reference for DAX (always quoted, which DAX accepts for any name)."""
    return "'" + name.replace("'", "''") + "'"


def doc_comment(text: str, indent: str) -> list[str]:
    """TMDL description (/// lines) above an object."""
    return [f"{indent}/// {line}" for line in text.splitlines()] if text else []


def table_tmdl(table: Table) -> str:
    """Render one table file."""
    lines: list[str] = [*doc_comment(table.description, ""), f"table {tmdl_name(table.name)}"]
    if table.hidden:
        lines.append("\tisHidden")
    if table.data_category:
        lines.append(f"\tdataCategory: {table.data_category}")
    lines.append(f"\tlineageTag: {stable_id('table', table.name)}")
    lines.append("")
    for measure in table.measures:
        lines.extend(doc_comment(measure.description, "\t"))
        lines.append(f"\tmeasure {tmdl_name(measure.name)} = {measure.expression}")
        lines.append(f"\t\tformatString: {measure.format_string}")
        lines.append(f"\t\tdisplayFolder: {measure.folder}")
        if measure.hidden:
            lines.append("\t\tisHidden")
        lines.append(f"\t\tlineageTag: {stable_id('measure', table.name, measure.name)}")
        lines.append("")
    for column in table.columns:
        lines.extend(doc_comment(column.description, "\t"))
        lines.append(f"\tcolumn {tmdl_name(column.name)}")
        lines.append(f"\t\tdataType: {column.data_type}")
        if column.is_key:
            lines.append("\t\tisKey")
        if column.hidden:
            lines.append("\t\tisHidden")
        if column.format_string:
            lines.append(f"\t\tformatString: {column.format_string}")
        if column.data_category:
            lines.append(f"\t\tdataCategory: {column.data_category}")
        lines.append(f"\t\tlineageTag: {stable_id('column', table.name, column.name)}")
        lines.append(f"\t\tsummarizeBy: {column.summarize_by}")
        lines.append(f"\t\tsourceColumn: {column.name}")
        if column.sort_by:
            lines.append(f"\t\tsortByColumn: {tmdl_name(column.sort_by)}")
        lines.append("")
        lines.append("\t\tannotation SummarizationSetBy = Automatic")
        lines.append("")
    lines.extend(
        [
            f"\tpartition {tmdl_name(table.name)} = m",
            "\t\tmode: directQuery",
            "\t\tsource =",
            "\t\t\t\tlet",
            '\t\t\t\t    Source = PostgreSQL.Database(DbHost & ":" & Number.ToText(DbPort), DbName),',
            f'\t\t\t\t    Data = Source{{[Schema = "bi", Item = "{table.view}"]}}[Data]',
            "\t\t\t\tin",
            "\t\t\t\t    Data",
            "",
            "\tannotation PBI_ResultType = Table",
            "",
        ]
    )
    return "\n".join(lines)


def model_files() -> dict[str, str]:
    """All files of the semantic model, keyed by path relative to MODEL_DIR."""
    files: dict[str, str] = {}
    files["definition.pbism"] = json_text(
        {"$schema": SCHEMAS["pbism"], "version": "4.2", "settings": {}}
    )
    files[".platform"] = json_text(
        {
            "$schema": SCHEMAS["platform"],
            "metadata": {"type": "SemanticModel", "displayName": PROJECT_NAME},
            "config": {"version": "2.0", "logicalId": stable_id("semanticModel")},
        }
    )
    files["definition/database.tmdl"] = "database\n\tcompatibilityLevel: 1600\n"
    query_order = [name for name, *_ in PARAMETERS] + [table.name for table in TABLES]
    model_lines = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "queryGroup Parameters",
        "",
        "\tannotation PBI_QueryGroupOrder = 0",
        "",
        f"annotation PBI_QueryOrder = {json.dumps(query_order)}",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = 0",
        "",
        'annotation PBI_ProTooling = ["DevMode"]',
        "",
        *[f"ref table {tmdl_name(table.name)}" for table in TABLES],
        "",
        *[f"ref role {tmdl_name(role_name(borough))}" for borough in BOROUGHS],
        "",
        "ref cultureInfo en-US",
        "",
    ]
    files["definition/model.tmdl"] = "\n".join(model_lines)
    expression_lines: list[str] = []
    for name, value, kind, description in PARAMETERS:
        expression_lines.extend(doc_comment(description, ""))
        expression_lines.append(
            f'expression {name} = {value} meta [IsParameterQuery = true, Type = "{kind}", IsParameterQueryRequired = true]'
        )
        expression_lines.append(f"\tlineageTag: {stable_id('parameter', name)}")
        expression_lines.append("\tqueryGroup: Parameters")
        expression_lines.append("")
        expression_lines.append(f"\tannotation PBI_ResultType = {kind}")
        expression_lines.append("")
    files["definition/expressions.tmdl"] = "\n".join(expression_lines)
    relationship_lines: list[str] = []
    for from_table, from_column, to_table, to_column in RELATIONSHIPS:
        relationship_lines.append(
            f"relationship {stable_id('relationship', from_table, from_column)}"
        )
        relationship_lines.append(f"\tfromColumn: {tmdl_name(from_table)}.{tmdl_name(from_column)}")
        relationship_lines.append(f"\ttoColumn: {tmdl_name(to_table)}.{tmdl_name(to_column)}")
        relationship_lines.append("")
    files["definition/relationships.tmdl"] = "\n".join(relationship_lines)
    for borough in BOROUGHS:
        files[f"definition/roles/{role_name(borough)}.tmdl"] = "\n".join(
            [
                f"/// Sees only {borough} stations and their facts.",
                f"role {tmdl_name(role_name(borough))}",
                "\tmodelPermission: read",
                "",
                f'\ttablePermission Borough = [borough] = "{borough}"',
                "",
                f"\tannotation PBI_Id = {short_id('role', borough)}",
                "",
            ]
        )
    files["definition/cultures/en-US.tmdl"] = "cultureInfo en-US\n"
    for table in TABLES:
        files[f"definition/tables/{table.name}.tmdl"] = table_tmdl(table)
    return files


def role_name(borough: str) -> str:
    """Name of the RLS role for a borough."""
    return f"Borough - {borough}"


# ====================================================================== report helpers


def literal(value: str | bool | int | float) -> dict[str, Any]:
    """A PBIR literal expression. Strings are single-quoted, numbers use type suffixes."""
    if isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, int):
        text = f"{value}L"
    elif isinstance(value, float):
        text = f"{value}D"
    else:
        text = "'" + value.replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": text}}}


def field_ref(kind: str, entity: str, prop: str) -> dict[str, Any]:
    """A semantic-query field: kind is Column or Measure."""
    return {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure(entity: str, prop: str) -> tuple[str, str, str]:
    """Field shorthand for a measure."""
    return ("Measure", entity, prop)


def column(entity: str, prop: str) -> tuple[str, str, str]:
    """Field shorthand for a column."""
    return ("Column", entity, prop)


def projection(field: tuple[str, str, str], display_name: str | None = None) -> dict[str, Any]:
    """A role projection."""
    kind, entity, prop = field
    result: dict[str, Any] = {
        "field": field_ref(kind, entity, prop),
        "queryRef": f"{entity}.{prop}",
        "nativeQueryRef": display_name or prop,
    }
    if display_name:
        result["displayName"] = display_name
    return result


@dataclass
class Visual:
    """A visual on a page: type, data roles, position, and title."""

    key: str
    visual_type: str
    title: str
    x: int
    y: int
    width: int
    height: int
    roles: dict[str, list[tuple[str, str, str] | tuple[tuple[str, str, str], str]]] = field(
        default_factory=dict
    )
    sort: tuple[tuple[str, str, str], str] | None = None
    filters: list[dict[str, Any]] = field(default_factory=list)
    objects: dict[str, Any] = field(default_factory=dict)


def visual_json(page_key: str, visual: Visual, z: int) -> dict[str, Any]:
    """Render a visual container."""
    query_state: dict[str, Any] = {}
    for role, fields in visual.roles.items():
        projections = []
        for item in fields:
            if isinstance(item[0], tuple):
                field_tuple, display = item
                projections.append(projection(field_tuple, display))
            else:
                projections.append(projection(item))
        query_state[role] = {"projections": projections}
    visual_body: dict[str, Any] = {"visualType": visual.visual_type}
    if query_state:
        query: dict[str, Any] = {"queryState": query_state}
        if visual.sort:
            (kind, entity, prop), direction = visual.sort
            query["sortDefinition"] = {
                "sort": [{"field": field_ref(kind, entity, prop), "direction": direction}],
                "isDefaultSort": True,
            }
        visual_body["query"] = query
    if visual.objects:
        visual_body["objects"] = visual.objects
    visual_body["visualContainerObjects"] = {
        "title": [
            {"properties": {"show": literal(bool(visual.title)), "text": literal(visual.title)}}
        ]
    }
    visual_body["drillFilterOtherVisuals"] = True
    container: dict[str, Any] = {
        "$schema": SCHEMAS["visual"],
        "name": short_id(page_key, visual.key),
        "position": {
            "x": visual.x,
            "y": visual.y,
            "z": z * 1000,
            "width": visual.width,
            "height": visual.height,
            "tabOrder": z * 1000,
        },
        "visual": visual_body,
    }
    if visual.filters:
        container["filterConfig"] = {"filters": visual.filters}
    return container


def exclude_filter(name: str, entity: str, prop: str, excluded: str) -> dict[str, Any]:
    """A categorical filter that keeps every value except ``excluded``."""
    return {
        "name": name,
        "field": field_ref("Column", entity, prop),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "t", "Entity": entity, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "Not": {
                            "Expression": {
                                "In": {
                                    "Expressions": [
                                        {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Source": "t"}},
                                                "Property": prop,
                                            }
                                        }
                                    ],
                                    "Values": [[{"Literal": {"Value": "'" + excluded + "'"}}]],
                                }
                            }
                        }
                    }
                }
            ],
        },
    }


def card(
    key_: str, title: str, value: tuple[str, str, str], x: int, y: int, width: int = 200
) -> Visual:
    """A single-number card."""
    return Visual(key_, "card", title, x, y, width, 110, {"Values": [value]})


def slicer(
    key_: str, title: str, value: tuple[str, str, str], x: int, y: int, width: int, height: int
) -> Visual:
    """A slicer."""
    return Visual(key_, "slicer", title, x, y, width, height, {"Values": [value]})


@dataclass
class Page:
    """A report page."""

    key: str
    display_name: str
    visuals: list[Visual]
    refresh_seconds: int | None = None


DISCLAIMER = (
    "Independent project. Not affiliated with Citi Bike or Lyft. Uses the public GBFS feed."
)

FS = "fleet_status"
SH = "station_hourly"

PAGES: list[Page] = [
    Page(
        "executive",
        "Executive Summary",
        [
            card("availability", "Availability rate", measure(SH, "availability_rate"), 20, 20),
            card("empty_share", "Empty share", measure(SH, "empty_share"), 230, 20),
            card("full_share", "Full share", measure(SH, "full_share"), 440, 20),
            card("bikes_added", "Bikes added", measure(SH, "bikes_added"), 650, 20),
            card(
                "chronic",
                "Chronic problem stations",
                measure("chronic_stations", "chronic_problem_stations"),
                860,
                20,
            ),
            slicer("date", "Date", column("Date", "calendar_date"), 1070, 20, 190, 110),
            Visual(
                "trend",
                "lineChart",
                "Availability rate by day and borough",
                20,
                150,
                760,
                330,
                {
                    "Category": [column("Date", "calendar_date")],
                    "Y": [measure(SH, "availability_rate")],
                    "Series": [column("Borough", "borough")],
                },
            ),
            Visual(
                "by_borough",
                "clusteredBarChart",
                "Availability rate by borough",
                800,
                150,
                460,
                330,
                {
                    "Category": [column("Borough", "borough")],
                    "Y": [measure(SH, "availability_rate")],
                },
                sort=(measure(SH, "availability_rate"), "Ascending"),
            ),
            Visual(
                "empty_full_by_hour",
                "clusteredColumnChart",
                "Empty and full share by hour of day",
                20,
                500,
                1240,
                200,
                {
                    "Category": [column("Hour", "hour_label")],
                    "Y": [measure(SH, "empty_share"), measure(SH, "full_share")],
                },
            ),
        ],
    ),
    Page(
        "live",
        "Live Operations",
        [
            card("bikes", "Bikes available", measure(FS, "bikes_available"), 20, 20, 170),
            card("ebikes", "E-bikes available", measure(FS, "ebikes_available"), 200, 20, 170),
            card("docks", "Docks available", measure(FS, "docks_available"), 380, 20, 170),
            card("empty", "Empty stations", measure(FS, "empty_stations"), 560, 20, 170),
            card("full", "Full stations", measure(FS, "full_stations"), 740, 20, 170),
            card(
                "in_service",
                "Stations in service",
                measure(FS, "stations_in_service"),
                920,
                20,
                170,
            ),
            card("freshness", "Data age (s)", measure(FS, "data_freshness_seconds"), 1100, 20, 160),
            Visual(
                "states",
                "clusteredBarChart",
                "Stations by imbalance state (labelled; colors fixed by the theme)",
                20,
                150,
                520,
                260,
                {"Category": [column(FS, "imbalance_state")], "Y": [measure(FS, "stations")]},
            ),
            Visual(
                "boroughs",
                "tableEx",
                "Right now by borough",
                560,
                150,
                700,
                260,
                {
                    "Values": [
                        column("Borough", "borough"),
                        measure(FS, "bikes_available"),
                        measure(FS, "docks_available"),
                        measure(FS, "fill_ratio"),
                        measure(FS, "empty_stations"),
                        measure(FS, "full_stations"),
                        measure(FS, "offline_stations"),
                    ]
                },
            ),
            Visual(
                "longest_empty",
                "tableEx",
                "High-traffic stations with no bikes",
                20,
                430,
                1240,
                270,
                {
                    "Values": [
                        column("Station", "station_name"),
                        column("Borough", "borough"),
                        column(FS, "is_high_traffic"),
                        measure(FS, "longest_empty_minutes"),
                        measure(FS, "empty_stations"),
                    ]
                },
                sort=(measure(FS, "longest_empty_minutes"), "Descending"),
                filters=[exclude_filter("highTraffic", FS, "imbalance_state", "offline")],
            ),
        ],
        refresh_seconds=30,
    ),
    Page(
        "stations",
        "Station Performance",
        [
            slicer("borough", "Borough", column("Borough", "borough"), 20, 20, 240, 200),
            slicer("dates", "Date", column("Date", "calendar_date"), 20, 240, 240, 110),
            Visual(
                "station_table",
                "tableEx",
                "Stations by availability (lowest first)",
                280,
                20,
                980,
                420,
                {
                    "Values": [
                        column("Station", "station_name"),
                        column("Station", "neighborhood"),
                        measure(SH, "availability_rate"),
                        measure(SH, "empty_share"),
                        measure(SH, "full_share"),
                        measure(SH, "bikes_added"),
                        measure(SH, "bikes_removed"),
                        measure(SH, "net_flow"),
                    ]
                },
                sort=(measure(SH, "availability_rate"), "Ascending"),
            ),
            Visual(
                "chronic_table",
                "tableEx",
                "Chronic verdicts (weekday peaks, last 14 days)",
                280,
                460,
                980,
                240,
                {
                    "Values": [
                        column("Station", "station_name"),
                        column("chronic_stations", "chronic_status"),
                        column("chronic_stations", "peak_hours_observed"),
                        column("chronic_stations", "peak_empty_share"),
                        column("chronic_stations", "peak_full_share"),
                    ]
                },
                filters=[
                    exclude_filter(
                        "ratedOnly", "chronic_stations", "chronic_status", "insufficient_data"
                    )
                ],
            ),
            card(
                "rated",
                "Stations with a verdict",
                measure("chronic_stations", "stations_rated"),
                20,
                370,
                240,
            ),
            card(
                "chronic_count",
                "Chronic problem stations",
                measure("chronic_stations", "chronic_problem_stations"),
                20,
                500,
                240,
            ),
        ],
    ),
    Page(
        "weather",
        "Weather Impact",
        [
            card(
                "temp",
                "Average temperature (°C)",
                measure("Weather", "avg_temperature_c"),
                20,
                20,
                300,
            ),
            card(
                "precip",
                "Precipitation (mm)",
                measure("Weather", "total_precipitation_mm"),
                340,
                20,
                300,
            ),
            card(
                "availability_w",
                "Availability rate",
                measure(SH, "availability_rate"),
                660,
                20,
                300,
            ),
            slicer("dates_w", "Date", column("Date", "calendar_date"), 980, 20, 280, 110),
            Visual(
                "by_condition",
                "clusteredBarChart",
                "Availability rate by weather condition",
                20,
                150,
                610,
                270,
                {
                    "Category": [column("Weather", "weather_condition")],
                    "Y": [measure(SH, "availability_rate")],
                },
            ),
            Visual(
                "by_band",
                "clusteredColumnChart",
                "Availability rate by temperature band",
                650,
                150,
                610,
                270,
                {
                    "Category": [column("Weather", "temperature_band")],
                    "Y": [measure(SH, "availability_rate")],
                },
            ),
            Visual(
                "flow_by_condition",
                "clusteredColumnChart",
                "Bikes added and removed by weather condition",
                20,
                440,
                1240,
                260,
                {
                    "Category": [column("Weather", "weather_condition")],
                    "Y": [measure(SH, "bikes_added"), measure(SH, "bikes_removed")],
                },
            ),
        ],
    ),
    Page(
        "rebalancing",
        "Rebalancing",
        [
            card("starving", "Starving stations", measure(FS, "starving_stations"), 20, 20, 240),
            card("flooding", "Flooding stations", measure(FS, "flooding_stations"), 280, 20, 240),
            card("to_move", "Bikes to move", measure(FS, "rebalance_need_bikes"), 540, 20, 240),
            card("fill", "Network fill ratio", measure(FS, "fill_ratio"), 800, 20, 220),
            slicer("borough_r", "Borough", column("Borough", "borough"), 1040, 20, 220, 110),
            Visual(
                "queue",
                "tableEx",
                "Visit next (ranked by bikes to move × typical demand)",
                20,
                150,
                820,
                550,
                {
                    "Values": [
                        column(FS, "priority_rank"),
                        column("Station", "station_name"),
                        column("Borough", "borough"),
                        column(FS, "recommended_action"),
                        column(FS, "bikes_to_move"),
                        column(FS, "imbalance_state"),
                        column(FS, "station_fill_ratio"),
                    ]
                },
                sort=(column(FS, "priority_rank"), "Ascending"),
                filters=[exclude_filter("needsVisit", FS, "recommended_action", "No action")],
            ),
            Visual(
                "need_by_borough",
                "clusteredBarChart",
                "Bikes to move by borough and state",
                860,
                150,
                400,
                550,
                {
                    "Category": [column("Borough", "borough")],
                    "Y": [measure(FS, "rebalance_need_bikes")],
                    "Series": [column(FS, "imbalance_state")],
                },
            ),
        ],
        refresh_seconds=60,
    ),
]


def page_json(page: Page) -> dict[str, Any]:
    """Render a page definition."""
    body: dict[str, Any] = {
        "$schema": SCHEMAS["page"],
        "name": short_id("page", page.key),
        "displayName": page.display_name,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
    }
    if page.refresh_seconds:
        # Automatic page refresh (DirectQuery). See VERIFY.md if Desktop shows it off.
        body["objects"] = {
            "pageRefresh": [
                {
                    "properties": {
                        "show": literal(True),
                        "duration": literal(f"PT{page.refresh_seconds}S"),
                    }
                }
            ]
        }
    return body


# ====================================================================== theme


def theme() -> dict[str, Any]:
    """The Dockline report theme (urban wayfinding)."""
    return {
        "name": "Dockline",
        "dataColors": [
            SIGNAL,
            STATE_COLORS["starving"],
            STATE_COLORS["flooding"],
            SLATE,
            STATE_COLORS["offline"],
            STATE_COLORS["balanced"],
            "#2E7D4F",
            "#8C5A2B",
        ],
        "foreground": INK,
        "foregroundNeutralSecondary": SLATE,
        "foregroundNeutralTertiary": "#7B8796",
        "background": SURFACE,
        "backgroundLight": PAPER,
        "backgroundNeutral": LINE,
        "tableAccent": SIGNAL,
        "good": "#2E7D4F",
        "neutral": STATE_COLORS["balanced"],
        "bad": STATE_COLORS["starving"],
        "maximum": STATE_COLORS["flooding"],
        "center": STATE_COLORS["balanced"],
        "minimum": STATE_COLORS["starving"],
        "textClasses": {
            "callout": {"fontSize": 28, "fontFace": "Archivo, Segoe UI", "color": INK},
            "title": {
                "fontSize": 13,
                "fontFace": "Archivo SemiBold, Segoe UI Semibold",
                "color": INK,
            },
            "header": {
                "fontSize": 12,
                "fontFace": "Archivo SemiBold, Segoe UI Semibold",
                "color": INK,
            },
            "label": {"fontSize": 10, "fontFace": "Archivo, Segoe UI", "color": SLATE},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"show": True, "color": {"solid": {"color": SURFACE}}}],
                    "border": [{"show": False}],
                    "dropShadow": [{"show": False}],
                    "title": [{"fontColor": {"solid": {"color": INK}}, "fontSize": 12}],
                }
            },
            "page": {
                "*": {"background": [{"color": {"solid": {"color": PAPER}}, "transparency": 0}]}
            },
        },
    }


# ====================================================================== report files


def report_files() -> dict[str, str]:
    """All files of the report, keyed by path relative to REPORT_DIR."""
    files: dict[str, str] = {}
    files["definition.pbir"] = json_text(
        {
            "$schema": SCHEMAS["pbir"],
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{PROJECT_NAME}.SemanticModel"}},
        }
    )
    files[".platform"] = json_text(
        {
            "$schema": SCHEMAS["platform"],
            "metadata": {"type": "Report", "displayName": PROJECT_NAME},
            "config": {"version": "2.0", "logicalId": stable_id("report")},
        }
    )
    files["definition/version.json"] = json_text(
        {"$schema": SCHEMAS["version"], "version": "2.0.0"}
    )
    files["definition/report.json"] = json_text(
        {
            "$schema": SCHEMAS["report"],
            "themeCollection": {
                "customTheme": {
                    "name": "Dockline.json",
                    "reportVersionAtImport": {
                        "visual": "2.13.0",
                        "report": "3.3.0",
                        "page": "2.1.0",
                    },
                    "type": "RegisteredResources",
                }
            },
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {"name": "Dockline.json", "path": "Dockline.json", "type": "CustomTheme"}
                    ],
                }
            ],
            "settings": {
                "useStylableVisualContainerHeader": True,
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
            },
        }
    )
    page_names = [short_id("page", page.key) for page in PAGES]
    files["definition/pages/pages.json"] = json_text(
        {"$schema": SCHEMAS["pages"], "pageOrder": page_names, "activePageName": page_names[0]}
    )
    for page in PAGES:
        page_name = short_id("page", page.key)
        files[f"definition/pages/{page_name}/page.json"] = json_text(page_json(page))
        for z, visual in enumerate(page.visuals):
            container = visual_json(page.key, visual, z)
            files[f"definition/pages/{page_name}/visuals/{container['name']}/visual.json"] = (
                json_text(container)
            )
    files["StaticResources/RegisteredResources/Dockline.json"] = json_text(theme())
    return files


def pbip_file() -> str:
    """The .pbip project file Power BI Desktop opens."""
    return json_text(
        {
            "$schema": SCHEMAS["pbip"],
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{PROJECT_NAME}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        }
    )


def json_text(value: Any) -> str:
    """Stable, readable JSON."""
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def measures_markdown() -> str:
    """powerbi/dax/measures.md: every DAX measure with its Cube twin."""
    lines = [
        "# DAX measures",
        "",
        "Generated by `powerbi/build_pbip.py` — do not edit by hand.",
        "",
        "Each measure has the same name as the Cube measure in the cube its table mirrors",
        "(`fleet_status`, `station_hourly`, `chronic_stations`, `weather`), so Power BI and",
        "Cube give the same answer for the same question. Definitions: `docs/metrics.md`.",
        "",
    ]
    for table in TABLES:
        if not table.measures:
            continue
        lines += [f"## {table.name} (Cube: `{table.cube}`)", "", table.description, ""]
        lines += [
            "| Measure | Folder | Format | DAX | Meaning |",
            "| --- | --- | --- | --- | --- |",
        ]
        for item in table.measures:
            name = f"`{item.name}`" + (" (hidden helper)" if item.hidden else "")
            dax = item.expression.replace("|", "\\|")
            lines.append(
                f"| {name} | {item.folder} | `{item.format_string}` | `{dax}` | {item.description} |"
            )
        lines.append("")
    lines += ["## Row-level security", "", "| Role | Filter |", "| --- | --- |"]
    lines += [f'| {role_name(b)} | `Borough[borough] = "{b}"` |' for b in BOROUGHS]
    lines.append("")
    return "\n".join(lines)


def render_all() -> dict[Path, str]:
    """Every generated file, keyed by absolute path."""
    files: dict[Path, str] = {
        ROOT / f"{PROJECT_NAME}.pbip": pbip_file(),
        THEME_PATH: json_text(theme()),
        ROOT / "dax" / "measures.md": measures_markdown(),
    }
    files.update({MODEL_DIR / path: text for path, text in model_files().items()})
    files.update({REPORT_DIR / path: text for path, text in report_files().items()})
    return files


def main() -> None:
    """Write the project, removing stale generated files."""
    for directory in (
        MODEL_DIR / "definition",
        REPORT_DIR / "definition",
        REPORT_DIR / "StaticResources",
    ):
        if directory.exists():
            shutil.rmtree(directory)
    for path, text in render_all().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    print(f"wrote {len(render_all())} files under {ROOT}")


if __name__ == "__main__":
    main()
