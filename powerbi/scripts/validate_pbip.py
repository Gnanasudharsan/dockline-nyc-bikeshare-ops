"""Validate the Dockline Power BI project without Power BI Desktop.

Checks:
1. Every PBIP/PBIR JSON file validates against Microsoft's published JSON schema named
   in its ``$schema`` (microsoft/json-schemas, pinned commit; fetched once into a cache).
2. The report theme validates against Microsoft's report theme schema.
3. Every field a visual uses (projections, sorts, filters) exists in the TMDL model as
   the right kind of object (column vs measure), and every relationship, sort-by column,
   and row-level security filter points at a real column.

TMDL syntax itself is checked with Microsoft's serializer (``make powerbi-validate``
runs powerbi/tools/tmdl-validator in Docker), which this script does not duplicate.

Usage: ``uv run python powerbi/scripts/validate_pbip.py``. Exit code 0 when valid.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

POWERBI_DIR = Path(__file__).resolve().parents[1]
MODEL_DEFINITION = POWERBI_DIR / "Dockline.SemanticModel" / "definition"
CACHE_DIR = Path(
    os.environ.get("PBIP_SCHEMA_CACHE", POWERBI_DIR.parent / ".cache" / "powerbi-schemas")
)

# Pinned sources (update deliberately, together with the schema versions in build_pbip.py).
JSON_SCHEMAS_REPO = "https://github.com/microsoft/json-schemas.git"
JSON_SCHEMAS_COMMIT = "eecc60d35b9ab18b884d35c50abe7d09d2753cdf"
THEME_SCHEMA_URL = (
    "https://raw.githubusercontent.com/microsoft/powerbi-desktop-samples/"
    "e2f326b09bb7df6890fff0ded9813a0d73677cd6/Report%20Theme%20JSON%20Schema/reportThemeSchema-2.159.json"
)
SCHEMA_URL_PREFIX = "https://developer.microsoft.com/json-schemas/"


# ---------------------------------------------------------------- schema cache


def ensure_schema_cache() -> Path:
    """Fetch the pinned microsoft/json-schemas checkout (fabric/ only) if missing."""
    repo = CACHE_DIR / "json-schemas"
    marker = repo / ".dockline-commit"
    if marker.exists() and marker.read_text().strip() == JSON_SCHEMAS_COMMIT:
        return repo
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        subprocess.run(  # noqa: S603 - fixed arguments
            [
                "git",
                "clone",
                "--quiet",
                "--filter=blob:none",
                "--no-checkout",
                JSON_SCHEMAS_REPO,
                str(repo),
            ],  # noqa: S607
            check=True,
        )
    subprocess.run(["git", "-C", str(repo), "sparse-checkout", "set", "fabric"], check=True)  # noqa: S603,S607
    subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), "checkout", "--quiet", JSON_SCHEMAS_COMMIT],  # noqa: S607
        check=True,
    )
    marker.write_text(JSON_SCHEMAS_COMMIT)
    return repo


def theme_schema() -> dict[str, Any]:
    """Return Microsoft's report theme schema (cached)."""
    path = CACHE_DIR / "reportThemeSchema-2.159.json"
    if not path.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(THEME_SCHEMA_URL, timeout=60) as response:  # noqa: S310
            path.write_bytes(response.read())
    loaded: dict[str, Any] = json.loads(path.read_text())
    return loaded


def make_registry(repo: Path) -> Registry:
    """Resolve developer.microsoft.com schema URLs to the local checkout."""

    def retrieve(uri: str) -> Resource:
        if not uri.startswith(SCHEMA_URL_PREFIX):
            raise NoSuchResource(uri)
        local = repo / uri.removeprefix(SCHEMA_URL_PREFIX)
        if not local.exists():
            raise NoSuchResource(uri)
        return Resource.from_contents(json.loads(local.read_text()))

    return Registry(retrieve=retrieve)  # type: ignore[call-arg]


# ---------------------------------------------------------------- TMDL model index


def model_index() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (columns by table, measures by table) parsed from the TMDL table files."""
    columns: dict[str, set[str]] = {}
    measures: dict[str, set[str]] = {}
    for path in sorted((MODEL_DEFINITION / "tables").glob("*.tmdl")):
        table = None
        for line in path.read_text().splitlines():
            if match := re.match(r"^table (.+)$", line):
                table = unquote(match.group(1))
                columns[table] = set()
                measures[table] = set()
            elif table and (match := re.match(r"^\tcolumn (.+)$", line)):
                columns[table].add(unquote(match.group(1)))
            elif table and (match := re.match(r"^\tmeasure (.+?) = ", line)):
                measures[table].add(unquote(match.group(1)))
    return columns, measures


def unquote(name: str) -> str:
    """Strip TMDL single quotes."""
    name = name.strip()
    if name.startswith("'") and name.endswith("'"):
        return name[1:-1].replace("''", "'")
    return name


def field_references(
    node: Any, aliases: dict[str, str] | None = None
) -> list[tuple[str, str, str]]:
    """Find every (kind, entity, property) referenced anywhere in a PBIR JSON tree."""
    found: list[tuple[str, str, str]] = []
    aliases = dict(aliases or {})
    if isinstance(node, dict):
        if "From" in node and isinstance(node["From"], list):
            for source in node["From"]:
                aliases[source.get("Name", "")] = source.get("Entity", "")
        for kind in ("Column", "Measure"):
            ref = node.get(kind)
            if isinstance(ref, dict) and "Property" in ref:
                source_ref = ref.get("Expression", {}).get("SourceRef", {})
                entity = source_ref.get("Entity") or aliases.get(source_ref.get("Source", ""), "")
                found.append((kind, entity, ref["Property"]))
        for value in node.values():
            found.extend(field_references(value, aliases))
    elif isinstance(node, list):
        for value in node:
            found.extend(field_references(value, aliases))
    return found


# ---------------------------------------------------------------- checks


def check_schemas(repo: Path) -> list[str]:
    """Validate every PBIP/PBIR JSON file that declares a $schema."""
    errors: list[str] = []
    registry = make_registry(repo)
    candidates = [POWERBI_DIR / "Dockline.pbip"]
    for folder in ("Dockline.Report", "Dockline.SemanticModel"):
        candidates.extend(
            p for p in (POWERBI_DIR / folder).rglob("*") if p.is_file() and p.suffix != ".tmdl"
        )
    for path in sorted(candidates):
        if "StaticResources" in path.parts:
            continue
        document = json.loads(path.read_text())
        schema_url = document.get("$schema")
        if not schema_url:
            errors.append(f"{path.relative_to(POWERBI_DIR)}: no $schema")
            continue
        schema = registry.get_or_retrieve(schema_url).value.contents
        validator = Draft7Validator(schema, registry=registry)
        for error in validator.iter_errors(document):
            location = "/".join(str(part) for part in error.absolute_path)
            errors.append(f"{path.relative_to(POWERBI_DIR)}: {location}: {error.message[:200]}")
    return errors


def check_theme() -> list[str]:
    """Validate the theme against the report theme schema."""
    errors: list[str] = []
    validator = Draft7Validator(theme_schema())
    for path in (
        POWERBI_DIR / "theme" / "dockline.json",
        POWERBI_DIR
        / "Dockline.Report"
        / "StaticResources"
        / "RegisteredResources"
        / "Dockline.json",
    ):
        for error in validator.iter_errors(json.loads(path.read_text())):
            location = "/".join(str(part) for part in error.absolute_path)
            errors.append(f"{path.relative_to(POWERBI_DIR)}: {location}: {error.message[:200]}")
    return errors


def check_fields() -> tuple[list[str], int]:
    """Check every report field reference against the model. Returns (errors, count)."""
    columns, measures = model_index()
    errors: list[str] = []
    count = 0
    for path in sorted((POWERBI_DIR / "Dockline.Report" / "definition").rglob("*.json")):
        for kind, entity, prop in field_references(json.loads(path.read_text())):
            count += 1
            pool = columns if kind == "Column" else measures
            if entity not in pool:
                errors.append(f"{path.relative_to(POWERBI_DIR)}: unknown table {entity!r}")
            elif prop not in pool[entity]:
                errors.append(
                    f"{path.relative_to(POWERBI_DIR)}: {kind.lower()} {entity}[{prop}] not in model"
                )
    return errors, count


def check_model_references() -> list[str]:
    """Relationships, sort-by columns, and RLS filters must point at real columns."""
    columns, _ = model_index()
    errors: list[str] = []
    relationships = (MODEL_DEFINITION / "relationships.tmdl").read_text()
    for table, column in re.findall(r"(?:from|to)Column: (\S+?)\.(\S+)", relationships):
        if unquote(column) not in columns.get(unquote(table), set()):
            errors.append(f"relationship references missing column {table}.{column}")
    for path in (MODEL_DEFINITION / "tables").glob("*.tmdl"):
        table_name = unquote(re.search(r"^table (.+)$", path.read_text(), re.M).group(1))  # type: ignore[union-attr]
        for target in re.findall(r"sortByColumn: (.+)", path.read_text()):
            if unquote(target) not in columns[table_name]:
                errors.append(f"{path.name}: sortByColumn {target} missing")
    for path in (MODEL_DEFINITION / "roles").glob("*.tmdl"):
        for table, column in re.findall(r"tablePermission (\S+) = \[(\w+)\]", path.read_text()):
            if column not in columns.get(unquote(table), set()):
                errors.append(f"{path.name}: RLS filter on missing column {table}[{column}]")
    return errors


def main() -> int:
    """Run every check and print a summary."""
    repo = ensure_schema_cache()
    schema_errors = check_schemas(repo)
    theme_errors = check_theme()
    field_errors, field_count = check_fields()
    model_errors = check_model_references()
    print(f"schemas: {'OK' if not schema_errors else f'{len(schema_errors)} error(s)'}")
    print(f"theme:   {'OK' if not theme_errors else f'{len(theme_errors)} error(s)'}")
    print(
        f"fields:  {field_count} references, {'OK' if not field_errors else f'{len(field_errors)} error(s)'}"
    )
    print(f"model:   {'OK' if not model_errors else f'{len(model_errors)} error(s)'}")
    for error in schema_errors + theme_errors + field_errors + model_errors:
        print(f"  - {error}")
    return 1 if (schema_errors or theme_errors or field_errors or model_errors) else 0


if __name__ == "__main__":
    sys.exit(main())
