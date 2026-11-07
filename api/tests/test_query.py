"""Strict validation of untrusted planner output."""

from typing import Any

import pytest

from dockline_api.catalog import SUGGESTED_QUESTIONS, TOPICS
from dockline_api.query import PlanError, nearest_question, parse_plan, validate_plan


def plan(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"supported": True, "topic": "live", "measures": ["empty_stations"]}
    return base | overrides


def test_valid_live_plan_builds_a_cube_query() -> None:
    validated = validate_plan(
        parse_plan(
            plan(
                dimensions=["borough"],
                filters=[
                    {"member": "imbalance_state", "operator": "equals", "values": ["STARVING"]}
                ],
            )
        )
    )
    assert validated.cube_query == {
        "measures": ["fleet_status.empty_stations"],
        "dimensions": ["fleet_status.borough"],
        "filters": [
            {"member": "fleet_status.imbalance_state", "operator": "equals", "values": ["starving"]}
        ],
        "limit": 10,
        "order": {"fleet_status.empty_stations": "desc"},
    }


def test_history_plan_gets_a_time_dimension() -> None:
    validated = validate_plan(
        parse_plan(
            plan(
                topic="history",
                measures=["availability_rate"],
                time_range="last 7 days",
                granularity="day",
            )
        )
    )
    assert validated.cube_query["timeDimensions"] == [
        {
            "dimension": "station_hourly.hour_start",
            "dateRange": "from 7 days ago to now",
            "granularity": "day",
        }
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"topic": "raw"}, "unknown topic"),
        ({"measures": ["revenue"]}, "not a measure"),
        ({"measures": ["fleet_status.empty_stations"]}, "not a measure"),
        ({"measures": []}, "at least one measure"),
        ({"dimensions": ["station_id"]}, "not a dimension"),
        ({"topic": "live", "measures": ["availability_rate"]}, "not a measure of the live topic"),
        ({"time_range": "last 7 days"}, "cannot have a time range"),
        (
            {"filters": [{"member": "borough", "operator": "equals", "values": ["Atlantis"]}]},
            "not a known borough",
        ),
        (
            {"filters": [{"member": "borough", "operator": "contains", "values": ["Man"]}]},
            "use equals",
        ),
        ({"order": {"member": "docks_available", "direction": "desc"}}, "selected measure"),
        ({"measures": ["empty_stations", "empty_stations"]}, "duplicate"),
    ],
)
def test_rejects_anything_outside_the_catalog(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(PlanError, match=message):
        validate_plan(parse_plan(plan(**overrides)))


@pytest.mark.parametrize(
    "raw",
    [
        plan(sql="SELECT * FROM raw.station_status"),
        plan(filters=[{"member": "borough", "operator": "in", "values": ["Queens"]}]),
        plan(limit=10_000),
        plan(measures=["a", "b", "c", "d", "e"]),
        plan(filters=[{"member": "neighborhood", "operator": "equals", "values": [], "extra": 1}]),
        {"supported": "yes please"},
    ],
)
def test_schema_rejects_extra_keys_and_bad_types(raw: dict[str, Any]) -> None:
    with pytest.raises(PlanError):
        parse_plan(raw)


def test_free_text_filter_values_are_length_limited() -> None:
    with pytest.raises(PlanError):
        validate_plan(
            parse_plan(
                plan(
                    filters=[
                        {"member": "station_name", "operator": "contains", "values": ["x" * 81]}
                    ]
                )
            )
        )


def test_refusal_suggestion_is_one_of_the_fixed_questions() -> None:
    assert (
        nearest_question(parse_plan({"supported": False, "nearest_question": 0}))
        == SUGGESTED_QUESTIONS[0]
    )
    assert nearest_question(parse_plan({"supported": False, "nearest_question": 999})) is None


def test_every_catalog_member_maps_to_a_cube_member_of_a_known_cube() -> None:
    cubes = {"fleet_status", "station_hourly", "chronic_stations", "stations", "weather", "dates"}
    for topic in TOPICS.values():
        for member in list(topic.measures.values()) + list(topic.dimensions.values()):
            assert member.cube_member.split(".")[0] in cubes, member.cube_member


def test_every_time_range_maps_to_a_cube_date_range() -> None:
    from dockline_api.query import CUBE_DATE_RANGES

    assert set(TOPICS["history"].time_ranges) <= set(CUBE_DATE_RANGES)
