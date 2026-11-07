"""Smoke-test every provisioned dashboard query against a running Grafana.

For each panel target (and template variable) in grafana/dashboards/*.json, send the
query through Grafana's /api/ds/query endpoint, exactly as a browser would, so Grafana
macros are expanded and the query goes through the real datasource (Cube's SQL API or
the warehouse). Also checks that datasources are healthy and alert rules are loaded.

Exit code 0 when every query succeeds. Queries that legitimately return no rows (for
example a filtered alert-style table) are reported but not failures.

Usage: ``python3 grafana/check_dashboards.py`` (stdlib only). Reads GRAFANA_URL
(default http://localhost:3060), GRAFANA_ADMIN_USER, GRAFANA_ADMIN_PASSWORD.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboards"
EXPECTED_ALERT_RULES = {
    "dockline-feed-stale",
    "dockline-high-traffic-empty",
    "dockline-ingestion-failure",
}


class Grafana:
    """Minimal Grafana HTTP API client using basic auth."""

    def __init__(self, url: str, user: str, password: str) -> None:
        """Store the base URL and the basic-auth header."""
        self.url = url.rstrip("/")
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    def request(self, method: str, path: str, body: Any = None) -> Any:
        """Send a request and return the decoded JSON response."""
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(  # noqa: S310 - URL comes from our own config
            self.url + path, data=data, headers=self.headers, method=method
        )
        with urllib.request.urlopen(req, timeout=60) as response:  # noqa: S310
            return json.loads(response.read() or b"null")


def substitute(sql: str, variables: dict[str, str]) -> str:
    """Replace ${name} template variables with sample values."""
    for name, value in variables.items():
        sql = sql.replace("${" + name + "}", value)
    return sql


def run_query(
    grafana: Grafana, target: dict[str, Any], variables: dict[str, str]
) -> tuple[bool, int, str]:
    """Run one target over the last 6 hours. Returns (ok, row_count, error)."""
    body = {
        "from": "now-6h",
        "to": "now",
        "queries": [{**target, "rawSql": substitute(target["rawSql"], variables), "refId": "A"}],
    }
    try:
        result = grafana.request("POST", "/api/ds/query", body)
    except urllib.error.HTTPError as error:
        return False, 0, error.read().decode(errors="replace")[:300]
    frame_result = result["results"]["A"]
    if frame_result.get("error"):
        return False, 0, str(frame_result["error"])[:300]
    rows = 0
    for frame in frame_result.get("frames", []):
        values = frame.get("data", {}).get("values", [])
        rows += len(values[0]) if values else 0
    return True, rows, ""


def sample_variables(grafana: Grafana) -> dict[str, str]:
    """Resolve template variables to realistic values via the same datasources."""
    overview = json.loads((DASHBOARD_DIR / "live-network-overview.json").read_text())
    at_bucket_query = next(v for v in overview["templating"]["list"] if v["name"] == "at_bucket")
    at_sql = at_bucket_query["query"].replace("'${__to:date:iso}'", "now()")
    _, _, _ = run_query(
        grafana,
        {"datasource": at_bucket_query["datasource"], "rawSql": at_sql, "format": "table"},
        {},
    )
    body = {
        "from": "now-1h",
        "to": "now",
        "queries": [
            {
                "refId": "A",
                "datasource": at_bucket_query["datasource"],
                "rawSql": at_sql,
                "format": "table",
            }
        ],
    }
    at_bucket = grafana.request("POST", "/api/ds/query", body)["results"]["A"]["frames"][0]["data"][
        "values"
    ][0][0]
    station_body = {
        "from": "now-1h",
        "to": "now",
        "queries": [
            {
                "refId": "A",
                "datasource": {"type": "grafana-postgresql-datasource", "uid": "cube"},
                "rawSql": "SELECT station_id FROM fleet_status WHERE priority_rank = 1 GROUP BY 1",
                "format": "table",
            }
        ],
    }
    station = grafana.request("POST", "/api/ds/query", station_body)["results"]["A"]["frames"][0][
        "data"
    ]["values"][0][0]
    return {"at_bucket": at_bucket, "station": station}


def main() -> int:
    """Check datasources, alert rules, and every dashboard query."""
    grafana = Grafana(
        os.environ.get("GRAFANA_URL", "http://localhost:3060"),
        os.environ.get("GRAFANA_ADMIN_USER", "admin"),
        os.environ["GRAFANA_ADMIN_PASSWORD"],
    )
    failures = 0
    for uid in ("cube", "warehouse"):
        health = grafana.request("GET", f"/api/datasources/uid/{uid}/health")
        ok = health.get("status") == "OK"
        failures += not ok
        print(f"datasource {uid:<10} {'OK' if ok else 'FAIL'}  {health.get('message', '')}")

    rules = {rule["uid"] for rule in grafana.request("GET", "/api/v1/provisioning/alert-rules")}
    missing = EXPECTED_ALERT_RULES - rules
    failures += bool(missing)
    print(
        f"alert rules: {len(rules & EXPECTED_ALERT_RULES)}/{len(EXPECTED_ALERT_RULES)} provisioned"
        + (f", missing {sorted(missing)}" if missing else "")
    )

    variables = sample_variables(grafana)
    print(f"sample variables: {variables}")
    for path in sorted(DASHBOARD_DIR.glob("*.json")):
        model = json.loads(path.read_text())
        loaded = grafana.request("GET", f"/api/dashboards/uid/{model['uid']}")
        print(f"\n{model['title']} ({path.name}) provisioned v{loaded['dashboard']['version']}")
        for panel in model["panels"]:
            for target in panel.get("targets", []):
                ok, rows, error = run_query(grafana, target, variables)
                failures += not ok
                status = "OK  " if ok else "FAIL"
                print(
                    f"  {status} {rows:>5} rows  {panel['title']}"
                    + (f"\n         {error}" if error else "")
                )
    print(f"\n{'All dashboard queries succeeded.' if failures == 0 else f'{failures} failure(s).'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
