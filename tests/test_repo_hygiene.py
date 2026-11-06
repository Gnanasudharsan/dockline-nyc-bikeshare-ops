"""Repository hygiene rules that every phase must keep passing.

These tests turn the project's operating rules into checks:
every Compose service is production-shaped (healthcheck, restart policy, resource
limits), every Compose variable is documented in .env.example, and secrets stay out of git.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILES = sorted(REPO_ROOT.glob("docker-compose*.yml")) + sorted(
    (REPO_ROOT / "infra").glob("docker-compose*.yml")
)
ENV_EXAMPLE = REPO_ROOT / ".env.example"

# Matches ${VAR}, ${VAR:-default}, ${VAR:?message} but not $${VAR},
# which Compose passes through to the container shell unchanged.
COMPOSE_VARIABLE = re.compile(r"(?<!\$)\$\{([A-Z_][A-Z0-9_]*)")
ALLOWED_RESTART_POLICIES = {"always", "unless-stopped", "on-failure"}


def load_services(compose_file: Path) -> dict[str, dict[str, Any]]:
    """Return the `services` mapping of a Compose file."""
    document = yaml.safe_load(compose_file.read_text())
    services: dict[str, dict[str, Any]] = document.get("services", {})
    return services


def env_example_keys() -> set[str]:
    """Return the variable names defined in .env.example."""
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            keys.add(stripped.split("=", 1)[0])
    return keys


def all_services() -> list[tuple[str, str, dict[str, Any]]]:
    """Return (file name, service name, service definition) for every service."""
    return [
        (path.name, name, service)
        for path in COMPOSE_FILES
        for name, service in load_services(path).items()
    ]


def test_compose_file_exists() -> None:
    assert (REPO_ROOT / "docker-compose.yml").is_file()


@pytest.mark.parametrize(("file_name", "service_name", "service"), all_services())
def test_service_has_healthcheck(
    file_name: str, service_name: str, service: dict[str, Any]
) -> None:
    if file_name != "docker-compose.yml":
        pytest.skip("override files may inherit the healthcheck from the base file")
    healthcheck = service.get("healthcheck", {})
    assert healthcheck.get("test"), f"{service_name} needs a healthcheck"
    assert not healthcheck.get("disable", False), f"{service_name} disables its healthcheck"


@pytest.mark.parametrize(("file_name", "service_name", "service"), all_services())
def test_service_has_restart_policy(
    file_name: str, service_name: str, service: dict[str, Any]
) -> None:
    if file_name != "docker-compose.yml":
        pytest.skip("override files may inherit the restart policy from the base file")
    restart = str(service.get("restart", "")).split(":")[0]
    assert restart in ALLOWED_RESTART_POLICIES, f"{service_name} needs a restart policy"


@pytest.mark.parametrize(("file_name", "service_name", "service"), all_services())
def test_service_has_resource_limits(
    file_name: str, service_name: str, service: dict[str, Any]
) -> None:
    if file_name != "docker-compose.yml":
        pytest.skip("override files may inherit limits from the base file")
    limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
    assert "memory" in limits, f"{service_name} needs a memory limit"
    assert "cpus" in limits, f"{service_name} needs a CPU limit"


def test_every_compose_variable_is_documented() -> None:
    documented = env_example_keys()
    referenced: set[str] = set()
    for path in COMPOSE_FILES:
        referenced |= set(COMPOSE_VARIABLE.findall(path.read_text()))
    missing = sorted(referenced - documented)
    assert not missing, f"Add these variables to .env.example: {missing}"


def test_postgres_not_bound_to_all_interfaces_by_default() -> None:
    documented = dict(
        line.split("=", 1)
        for line in ENV_EXAMPLE.read_text().splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    assert documented.get("POSTGRES_BIND_ADDRESS") == "127.0.0.1"


def test_env_file_is_gitignored() -> None:
    result = subprocess.run(  # noqa: S603 - fixed arguments, no user input
        ["git", "check-ignore", "--quiet", ".env"],  # noqa: S607 - git on PATH
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, ".env must be listed in .gitignore"


def test_env_example_has_no_real_secrets() -> None:
    for line in ENV_EXAMPLE.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")):
            assert value == "", f"{key} must be empty in .env.example"
