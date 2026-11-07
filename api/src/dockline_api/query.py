"""Strict validation: LLM plan → Cube query, or a rejection.

The planner's output is untrusted. It must parse into ``Plan`` (unknown keys are
errors), name a topic from the catalog, and use only that topic's members, operators,
values, and time ranges. Only then is a Cube REST query built. There is no code path
from a question to SQL.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dockline_api.catalog import SUGGESTED_QUESTIONS, TOPICS, Member, Topic

MAX_MEASURES = 4
MAX_DIMENSIONS = 2
MAX_FILTERS = 3
MAX_FILTER_VALUES = 7
MAX_VALUE_CHARS = 80
DEFAULT_LIMIT = 10
MAX_LIMIT = 50


# Cube's "last N days" excludes today; people asking "in the last 7 days" include it.
# Rolling ranges therefore run up to now.
CUBE_DATE_RANGES = {
    "today": "today",
    "yesterday": "yesterday",
    "last 24 hours": "from 24 hours ago to now",
    "last 7 days": "from 7 days ago to now",
    "last 14 days": "from 14 days ago to now",
    "this week": "this week",
    "last week": "last week",
    "this month": "this month",
}


class PlanFilter(BaseModel):
    """A filter on one dimension."""

    model_config = ConfigDict(extra="forbid")

    member: str
    operator: Literal["equals", "notEquals", "contains"]
    values: list[str] = Field(min_length=1, max_length=MAX_FILTER_VALUES)


class PlanOrder(BaseModel):
    """Sort by one selected member."""

    model_config = ConfigDict(extra="forbid")

    member: str
    direction: Literal["asc", "desc"] = "desc"


class Plan(BaseModel):
    """What the planner LLM must return (JSON)."""

    model_config = ConfigDict(extra="forbid")

    supported: bool
    topic: str | None = None
    measures: list[str] = Field(default_factory=list, max_length=MAX_MEASURES)
    dimensions: list[str] = Field(default_factory=list, max_length=MAX_DIMENSIONS)
    filters: list[PlanFilter] = Field(default_factory=list, max_length=MAX_FILTERS)
    time_range: str | None = None
    granularity: str | None = None
    order: PlanOrder | None = None
    limit: int | None = Field(default=None, ge=1, le=MAX_LIMIT)
    refusal_reason: str | None = Field(default=None, max_length=300)
    nearest_question: int | None = None


class PlanError(ValueError):
    """The plan broke a rule; the message says which (safe to show users)."""


class ValidatedQuery(BaseModel):
    """A plan that passed every check, plus the Cube query built from it."""

    topic: str
    measures: list[str]
    dimensions: list[str]
    filters: list[PlanFilter]
    time_range: str | None
    granularity: str | None
    cube_query: dict[str, Any]


def parse_plan(raw: dict[str, Any]) -> Plan:
    """Parse untrusted planner JSON into a Plan (PlanError on any schema problem)."""
    try:
        return Plan.model_validate(raw)
    except ValidationError as error:
        raise PlanError(
            f"planner output did not match the schema ({error.error_count()} problem(s))"
        ) from error


def nearest_question(plan: Plan) -> str | None:
    """Resolve the refusal suggestion index to the fixed question text."""
    if plan.nearest_question is None or not 0 <= plan.nearest_question < len(SUGGESTED_QUESTIONS):
        return None
    return SUGGESTED_QUESTIONS[plan.nearest_question]


def _member(topic: Topic, name: str, kind: str) -> Member:
    pool = topic.measures if kind == "measure" else topic.dimensions
    if name not in pool:
        raise PlanError(f"'{name}' is not a {kind} of the {topic.name} topic")
    return pool[name]


def _normalize_value(member: Member, value: str) -> str:
    value = " ".join(value.split())
    if not value or len(value) > MAX_VALUE_CHARS:
        raise PlanError(f"invalid filter value for {member.name}")
    if member.allowed_values is not None:
        by_lower = {allowed.lower(): allowed for allowed in member.allowed_values}
        if value.lower() not in by_lower:
            raise PlanError(f"'{value}' is not a known {member.name}")
        return by_lower[value.lower()]
    return value


def validate_plan(plan: Plan) -> ValidatedQuery:
    """Check a supported plan against the catalog and build the Cube query."""
    if not plan.supported:
        raise PlanError("plan is a refusal")
    if plan.topic not in TOPICS:
        raise PlanError(f"unknown topic {plan.topic!r}")
    topic = TOPICS[plan.topic]
    if not plan.measures:
        raise PlanError("a question must use at least one measure")
    if len(set(plan.measures)) != len(plan.measures) or len(set(plan.dimensions)) != len(
        plan.dimensions
    ):
        raise PlanError("duplicate members")

    measures = [_member(topic, name, "measure") for name in plan.measures]
    dimensions = [_member(topic, name, "dimension") for name in plan.dimensions]

    filters: list[PlanFilter] = []
    cube_filters: list[dict[str, Any]] = []
    for item in plan.filters:
        member = _member(topic, item.member, "dimension")
        if not member.filterable:
            raise PlanError(f"cannot filter on {member.name}")
        if item.operator == "contains" and member.allowed_values is not None:
            raise PlanError(f"use equals for {member.name}")
        values = [_normalize_value(member, value) for value in item.values]
        filters.append(PlanFilter(member=member.name, operator=item.operator, values=values))
        cube_filters.append(
            {"member": member.cube_member, "operator": item.operator, "values": values}
        )

    query: dict[str, Any] = {
        "measures": [m.cube_member for m in measures],
        "dimensions": [d.cube_member for d in dimensions],
        "filters": cube_filters,
        "limit": plan.limit or DEFAULT_LIMIT,
    }

    if topic.time_dimension is None:
        if plan.time_range or plan.granularity:
            raise PlanError("live questions cannot have a time range")
    else:
        if plan.time_range is not None and plan.time_range not in topic.time_ranges:
            raise PlanError(f"unsupported time range {plan.time_range!r}")
        if plan.granularity is not None and plan.granularity not in topic.granularities:
            raise PlanError(f"unsupported granularity {plan.granularity!r}")
        if plan.time_range or plan.granularity:
            time_dimension: dict[str, Any] = {"dimension": topic.time_dimension}
            # Without a range, use the last 14 days (Cube needs one for a granularity).
            time_dimension["dateRange"] = CUBE_DATE_RANGES[plan.time_range or "last 14 days"]
            if plan.granularity:
                time_dimension["granularity"] = plan.granularity
            query["timeDimensions"] = [time_dimension]

    if plan.order is not None:
        selected = {m.name: m.cube_member for m in measures + dimensions}
        if plan.order.member not in selected:
            raise PlanError("can only sort by a selected measure or dimension")
        query["order"] = {selected[plan.order.member]: plan.order.direction}
    elif dimensions:
        query["order"] = {measures[0].cube_member: "desc"}

    return ValidatedQuery(
        topic=topic.name,
        measures=[m.name for m in measures],
        dimensions=[d.name for d in dimensions],
        filters=filters,
        time_range=plan.time_range,
        granularity=plan.granularity,
        cube_query=query,
    )
