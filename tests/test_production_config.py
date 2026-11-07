"""Rules for the production override (infra/docker-compose.prod.yml)."""

import re
import stat
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT / "infra" / "docker-compose.prod.yml"


class ComposeLoader(yaml.SafeLoader):
    """SafeLoader that understands Compose's !override and !reset tags."""


def _passthrough(loader: yaml.SafeLoader, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


ComposeLoader.add_constructor("!override", _passthrough)
ComposeLoader.add_constructor("!reset", _passthrough)


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.load(path.read_text(), Loader=ComposeLoader)  # noqa: S506
    return data


# The only ports that may listen beyond localhost: Caddy's HTTP and HTTPS (duckdns mode).
PUBLIC_PORTS = {"caddy": {"80:80", "443:443"}}


def test_every_published_port_is_bound_to_localhost() -> None:
    for name, service in load(PROD)["services"].items():
        for port in service.get("ports", []):
            if str(port) in PUBLIC_PORTS.get(name, set()):
                continue
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port} beyond localhost"


def test_https_front_doors_are_opt_in_profiles() -> None:
    prod = load(PROD)["services"]
    assert prod["cloudflared"]["profiles"] == ["cloudflare"]
    assert prod["caddy"]["profiles"] == ["duckdns"]
    assert prod["duckdns"]["profiles"] == ["duckdns"]


def test_caddy_keeps_certificates_and_limits_ask() -> None:
    compose = load(PROD)
    assert "caddy_data:/data" in compose["services"]["caddy"]["volumes"]
    assert "caddy_data" in compose["volumes"]
    caddyfile = (ROOT / "infra" / "caddy" / "Caddyfile").read_text()
    assert "rate_limit" in caddyfile and "path /v1/ask" in caddyfile
    assert "flush_interval -1" in caddyfile  # SSE must not be buffered


def test_every_long_running_service_restarts_always() -> None:
    base = load(ROOT / "docker-compose.yml")["services"]
    prod = load(PROD)["services"]
    for name, service in base.items():
        if service.get("labels", {}).get("dockline.role") == "oneshot":
            continue
        assert prod.get(name, {}).get("restart") == "always", name


def test_production_only_services_have_healthchecks_and_limits() -> None:
    prod = load(PROD)["services"]
    for name in ("cloudflared", "caddy", "duckdns", "backup"):
        service = prod[name]
        assert "healthcheck" in service, name
        assert service["deploy"]["resources"]["limits"]["memory"], name


def test_every_production_variable_is_documented() -> None:
    documented = set(re.findall(r"^([A-Z0-9_]+)=", (ROOT / ".env.example").read_text(), re.M))
    used = set(re.findall(r"\$\{([A-Z0-9_]+)", PROD.read_text()))
    assert used <= documented, used - documented


def test_backup_scripts_are_executable_and_restore_never_overwrites() -> None:
    scripts = ["backup/backup.sh", "backup/healthcheck.sh", "backup/restore.sh"]
    scripts += ["duckdns/update.sh", "duckdns/healthcheck.sh"]
    for script in scripts:
        mode = (ROOT / "infra" / script).stat().st_mode
        assert mode & stat.S_IXUSR, script
    restore = (ROOT / "infra" / "backup" / "restore.sh").read_text()
    assert "already exists" in restore
    assert "timescaledb_pre_restore" in restore and "timescaledb_post_restore" in restore


def merged_services() -> dict[str, dict[str, Any]]:
    """Base services with the production override applied (shallow per key, as Compose does
    for the keys checked here)."""
    base = load(ROOT / "docker-compose.yml")["services"]
    prod = load(PROD)["services"]
    merged = {name: dict(service) for name, service in base.items()}
    for name, override in prod.items():
        merged.setdefault(name, {}).update(override)
    return merged


def test_every_merged_service_has_healthcheck_restart_and_limits() -> None:
    for name, service in merged_services().items():
        if service.get("labels", {}).get("dockline.role") == "oneshot":
            assert service.get("restart") == "no", name
            continue
        assert "healthcheck" in service, f"{name} has no healthcheck in production"
        assert service.get("restart") == "always", name
        assert service.get("deploy", {}).get("resources", {}).get("limits"), name
