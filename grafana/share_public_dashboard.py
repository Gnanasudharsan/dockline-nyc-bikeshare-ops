"""Ensure the public (embeddable) live dashboard is shared and print its URL.

Public dashboards cannot be provisioned from files, so this script creates the share
through Grafana's API if it does not exist yet (idempotent). Only
``dockline-public-live`` is ever shared; it has no template variables, which public
dashboards do not support.

Usage: ``python3 grafana/share_public_dashboard.py`` (stdlib only; reads GRAFANA_* env).
"""

from __future__ import annotations

import os
import sys
import urllib.error

from check_dashboards import Grafana

PUBLIC_DASHBOARD_UID = "dockline-public-live"


def main() -> int:
    """Create the share if missing and print the public URL."""
    base_url = os.environ.get(
        "GRAFANA_URL", f"http://localhost:{os.environ.get('GRAFANA_PORT', '3060')}"
    )
    grafana = Grafana(
        base_url,
        os.environ.get("GRAFANA_ADMIN_USER", "admin"),
        os.environ["GRAFANA_ADMIN_PASSWORD"],
    )
    path = f"/api/dashboards/uid/{PUBLIC_DASHBOARD_UID}/public-dashboards"
    try:
        share = grafana.request("GET", path)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        share = grafana.request(
            "POST",
            path,
            {
                "isEnabled": True,
                "timeSelectionEnabled": False,
                "annotationsEnabled": False,
                "share": "public",
            },
        )
    print(f"{base_url}/public-dashboards/{share['accessToken']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
