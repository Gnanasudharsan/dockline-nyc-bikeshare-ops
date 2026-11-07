"""The allowlist for Ask the Data: which certified Cube members a question may use.

The LLM never sees table names or SQL. It picks a *topic* and short member names from
this catalog; ``query.validate_plan`` maps them to Cube members and rejects anything
else. Definitions are the human contract from docs/metrics.md, returned with answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BOROUGHS = ("Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island", "Jersey City", "Hoboken")
IMBALANCE_STATES = ("starving", "balanced", "flooding", "offline")
WEATHER_CONDITIONS = ("Clear", "Cloudy", "Fog", "Drizzle", "Rain", "Snow", "Thunderstorm")
DAY_TYPES = ("Weekday", "Weekend")
CHRONIC_STATUSES = (
    "insufficient_data",
    "ok",
    "chronic_empty",
    "chronic_full",
    "chronic_empty_and_full",
)
RECOMMENDED_ACTIONS = ("Add bikes", "Remove bikes", "No action")


@dataclass(frozen=True)
class Member:
    """One measure or dimension the planner may use."""

    name: str  # short name the LLM uses
    cube_member: str  # fully qualified Cube member
    definition: str
    # For filterable dimensions: the closed set of allowed values (None = free text).
    allowed_values: tuple[str, ...] | None = None
    filterable: bool = False
    unit: str = ""


@dataclass(frozen=True)
class Topic:
    """A group of members that Cube can query together."""

    name: str
    description: str
    measures: dict[str, Member]
    dimensions: dict[str, Member]
    time_dimension: str | None = None  # Cube member; None = "right now" only
    granularities: tuple[str, ...] = ()
    time_ranges: tuple[str, ...] = ()
    examples: tuple[str, ...] = field(default_factory=tuple)


def _members(*items: Member) -> dict[str, Member]:
    return {item.name: item for item in items}


LIVE = Topic(
    name="live",
    description="The network right now (latest feed poll). No time ranges.",
    measures=_members(
        Member(
            "bikes_available",
            "fleet_status.bikes_available",
            "Bikes a rider could rent right now at in-service stations (includes e-bikes).",
        ),
        Member(
            "ebikes_available",
            "fleet_status.ebikes_available",
            "E-bikes a rider could rent right now.",
        ),
        Member(
            "docks_available",
            "fleet_status.docks_available",
            "Empty docks a rider could return a bike to right now.",
        ),
        Member(
            "fill_ratio",
            "fleet_status.fill_ratio",
            "bikes_available / (bikes_available + docks_available) over in-service stations.",
            unit="ratio",
        ),
        Member(
            "imbalance_index",
            "fleet_status.imbalance_index",
            "fill_ratio minus the 0.5 target; negative = starving, positive = flooding.",
            unit="ratio",
        ),
        Member("stations", "fleet_status.stations", "Stations listed in the feed."),
        Member(
            "stations_in_service",
            "fleet_status.stations_in_service",
            "Stations reporting within 30 minutes, installed, and renting or returning.",
        ),
        Member(
            "empty_stations",
            "fleet_status.empty_stations",
            "In-service stations with no bike to rent right now.",
        ),
        Member(
            "full_stations",
            "fleet_status.full_stations",
            "In-service stations with no free dock right now.",
        ),
        Member(
            "starving_stations",
            "fleet_status.starving_stations",
            "Stations with fill ≤ 20% or no bikes.",
        ),
        Member(
            "flooding_stations",
            "fleet_status.flooding_stations",
            "Stations with fill ≥ 80% or no docks.",
        ),
        Member(
            "offline_stations",
            "fleet_status.offline_stations",
            "Stations not in service (silent > 30 min, not installed, or closed).",
        ),
        Member(
            "rebalance_need_bikes",
            "fleet_status.rebalance_need_bikes",
            "Bikes to add plus bikes to remove to bring starving and flooding stations to half full.",
        ),
        Member(
            "longest_empty_minutes",
            "fleet_status.longest_empty_minutes",
            "Longest current empty spell among the stations in the group, in minutes.",
            unit="minutes",
        ),
        Member(
            "data_freshness_seconds",
            "fleet_status.data_freshness_seconds",
            "Seconds since the newest station report.",
            unit="seconds",
        ),
    ),
    dimensions=_members(
        Member(
            "borough",
            "fleet_status.borough",
            "Borough (or Jersey City / Hoboken).",
            BOROUGHS,
            filterable=True,
        ),
        Member(
            "neighborhood",
            "fleet_status.neighborhood",
            "NYC 2020 neighborhood (NTA).",
            filterable=True,
        ),
        Member("station_name", "fleet_status.station_name", "Station name.", filterable=True),
        Member(
            "imbalance_state",
            "fleet_status.imbalance_state",
            "starving, balanced, flooding, or offline.",
            IMBALANCE_STATES,
            filterable=True,
        ),
        Member(
            "recommended_action",
            "fleet_status.recommended_action",
            "Add bikes, Remove bikes, or No action.",
            RECOMMENDED_ACTIONS,
            filterable=True,
        ),
    ),
    examples=(
        "How many stations have no bikes right now?",
        "Which borough has the most empty stations right now?",
        "How many bikes are available in Brooklyn?",
        "Which stations need the most bikes moved right now?",
        "How fresh is the data?",
    ),
)

HISTORY = Topic(
    name="history",
    description="Hourly history: availability, empty and full time, bike flows.",
    measures=_members(
        Member(
            "availability_rate",
            "station_hourly.availability_rate",
            "Share of in-service station-minutes with at least one bike and one dock.",
            unit="ratio",
        ),
        Member(
            "empty_share",
            "station_hourly.empty_share",
            "Share of in-service station-minutes with no bike.",
            unit="ratio",
        ),
        Member(
            "full_share",
            "station_hourly.full_share",
            "Share of in-service station-minutes with no free dock.",
            unit="ratio",
        ),
        Member(
            "empty_station_minutes",
            "station_hourly.empty_station_minutes",
            "Minutes stations had no bike to rent while renting.",
            unit="minutes",
        ),
        Member(
            "full_station_minutes",
            "station_hourly.full_station_minutes",
            "Minutes stations had no free dock while returning.",
            unit="minutes",
        ),
        Member(
            "net_flow",
            "station_hourly.net_flow",
            "Change in bikes on hand (includes rebalancing trucks; not trips).",
        ),
        Member(
            "bikes_added",
            "station_hourly.bikes_added",
            "Sum of increases in bikes on hand (returns plus trucks dropping bikes).",
        ),
        Member(
            "bikes_removed",
            "station_hourly.bikes_removed",
            "Sum of decreases in bikes on hand (rentals plus trucks collecting bikes).",
        ),
    ),
    dimensions=_members(
        Member(
            "borough",
            "stations.borough",
            "Borough (or Jersey City / Hoboken).",
            BOROUGHS,
            filterable=True,
        ),
        Member(
            "neighborhood", "stations.neighborhood", "NYC 2020 neighborhood (NTA).", filterable=True
        ),
        Member("station_name", "stations.station_name", "Station name.", filterable=True),
        Member("hour_of_day", "station_hourly.hour_of_day", "Local hour of day, 0–23."),
        Member(
            "weather_condition",
            "weather.weather_condition",
            "Clear, Cloudy, Fog, Drizzle, Rain, Snow, Thunderstorm.",
            WEATHER_CONDITIONS,
            filterable=True,
        ),
        Member("temperature_band", "weather.temperature_band", "Temperature band in °C."),
        Member("day_type", "dates.day_type", "Weekday or Weekend.", DAY_TYPES, filterable=True),
    ),
    time_dimension="station_hourly.hour_start",
    granularities=("hour", "day", "week"),
    time_ranges=(
        "today",
        "yesterday",
        "last 24 hours",
        "last 7 days",
        "last 14 days",
        "this week",
        "last week",
        "this month",
    ),
    examples=(
        "What was the availability rate yesterday?",
        "Which borough had the lowest availability rate in the last 7 days?",
        "At what hour of the day are stations most often empty?",
        "How does rain affect availability?",
        "How many bikes were added in Manhattan today?",
    ),
)

CHRONIC = Topic(
    name="chronic",
    description="Stations that are chronically empty or full during weekday peaks (last 14 days).",
    measures=_members(
        Member(
            "chronic_problem_stations",
            "chronic_stations.chronic_problem_stations",
            "Stations empty or full for more than 25% of in-service weekday-peak minutes over 14 days (needs ≥ 10 peak hours).",
        ),
        Member(
            "stations_rated",
            "chronic_stations.stations_rated",
            "Stations with enough weekday-peak data for a verdict.",
        ),
    ),
    dimensions=_members(
        Member(
            "borough",
            "chronic_stations.borough",
            "Borough (or Jersey City / Hoboken).",
            BOROUGHS,
            filterable=True,
        ),
        Member(
            "neighborhood",
            "chronic_stations.neighborhood",
            "NYC 2020 neighborhood (NTA).",
            filterable=True,
        ),
        Member("station_name", "chronic_stations.station_name", "Station name.", filterable=True),
        Member(
            "chronic_status",
            "chronic_stations.chronic_status",
            "insufficient_data, ok, chronic_empty, chronic_full, chronic_empty_and_full.",
            CHRONIC_STATUSES,
            filterable=True,
        ),
    ),
    examples=(
        "How many chronic problem stations are there?",
        "Which borough has the most chronically empty stations?",
    ),
)

TOPICS: dict[str, Topic] = {topic.name: topic for topic in (LIVE, HISTORY, CHRONIC)}

# The fixed list a refusal may point to (the planner returns an index, never free text).
SUGGESTED_QUESTIONS: tuple[str, ...] = tuple(q for topic in TOPICS.values() for q in topic.examples)


def catalog_for_prompt() -> str:
    """Render the catalog as compact text for the planner prompt."""
    lines: list[str] = []
    for topic in TOPICS.values():
        lines.append(f"TOPIC {topic.name}: {topic.description}")
        lines.append("  measures:")
        lines.extend(f"    {m.name}: {m.definition}" for m in topic.measures.values())
        lines.append("  dimensions:")
        for d in topic.dimensions.values():
            values = f" Allowed values: {', '.join(d.allowed_values)}." if d.allowed_values else ""
            filterable = " (filterable)" if d.filterable else ""
            lines.append(f"    {d.name}{filterable}: {d.definition}{values}")
        if topic.time_dimension:
            lines.append(f"  time_range: one of {', '.join(topic.time_ranges)}")
            lines.append(f"  granularity: one of {', '.join(topic.granularities)}")
        else:
            lines.append("  time_range: must be null (live data only)")
    lines.append("SUGGESTED QUESTIONS (for refusals, refer to them by index):")
    lines.extend(f"  {index}: {question}" for index, question in enumerate(SUGGESTED_QUESTIONS))
    return "\n".join(lines)
