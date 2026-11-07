"""The Cube model is the single source of metric definitions (ADR 0003)."""

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CUBE_FILES = sorted((ROOT / "semantic" / "model" / "cubes").glob("*.yml"))

# Every metric named in the CLAUDE.md catalog must exist as a Cube measure.
CATALOG_METRICS = {
    "bikes_available",
    "ebikes_available",
    "docks_available",
    "fill_ratio",
    "empty_station_minutes",
    "full_station_minutes",
    "availability_rate",
    "imbalance_index",
    "net_flow",
    "rebalance_need_bikes",
    "chronic_problem_stations",
    "data_freshness_seconds",
}


def load_cubes() -> list[dict[str, Any]]:
    cubes: list[dict[str, Any]] = []
    for path in CUBE_FILES:
        cubes.extend(yaml.safe_load(path.read_text())["cubes"])
    return cubes


def test_every_catalog_metric_is_a_cube_measure() -> None:
    measures = {m["name"] for cube in load_cubes() for m in cube.get("measures", [])}
    assert measures >= CATALOG_METRICS, CATALOG_METRICS - measures


def test_cube_names_and_members_are_unique() -> None:
    cubes = load_cubes()
    names = [cube["name"] for cube in cubes]
    assert len(names) == len(set(names))
    for cube in cubes:
        members = [m["name"] for m in cube.get("measures", []) + cube.get("dimensions", [])]
        assert len(members) == len(set(members)), cube["name"]


def test_every_cube_has_a_primary_key_and_reads_a_dbt_relation() -> None:
    for cube in load_cubes():
        assert any(d.get("primary_key") for d in cube["dimensions"]), cube["name"]
        assert re.fullmatch(r"marts\.\w+", cube["sql_table"]), cube["sql_table"]


def test_ratio_metrics_divide_by_additive_sums() -> None:
    """Rates are computed from summed minutes, never averaged."""
    for cube in load_cubes():
        for measure in cube.get("measures", []):
            if measure["name"] in {"availability_rate", "empty_share", "full_share", "fill_ratio"}:
                assert measure["type"] == "number"
                assert "NULLIF" in measure["sql"]
                assert "::numeric" in measure["sql"]


def test_live_cube_refreshes_every_10_seconds() -> None:
    fleet = next(cube for cube in load_cubes() if cube["name"] == "fleet_status")
    assert fleet["refresh_key"] == {"every": "10 second"}
