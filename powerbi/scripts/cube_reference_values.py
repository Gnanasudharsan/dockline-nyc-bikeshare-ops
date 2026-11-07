"""Print reference values from Cube for checking Power BI (VERIFY.md, step 5).

Power BI's DAX measures have the same names as Cube's measures. Run this on the Mac
while Power BI Desktop is open in the VM; the numbers should match the matching cards
(live numbers drift by a few units between refreshes, which is expected).

Usage: ``make powerbi-reference`` (reads CUBEJS_SQL_USER / CUBEJS_SQL_PASSWORD from .env).
"""

from __future__ import annotations

import os
import sys

import psycopg

QUERIES = [
    (
        "Live Operations cards (fleet_status)",
        "SELECT MEASURE(bikes_available) AS bikes_available, MEASURE(ebikes_available) AS ebikes_available, "
        "MEASURE(docks_available) AS docks_available, MEASURE(empty_stations) AS empty_stations, "
        "MEASURE(full_stations) AS full_stations, MEASURE(stations_in_service) AS stations_in_service "
        "FROM fleet_status",
    ),
    (
        "Rebalancing cards (fleet_status)",
        "SELECT MEASURE(starving_stations) AS starving_stations, MEASURE(flooding_stations) AS flooding_stations, "
        "MEASURE(rebalance_need_bikes) AS rebalance_need_bikes, MEASURE(fill_ratio) AS fill_ratio FROM fleet_status",
    ),
    (
        "Right now by borough (Live Operations table)",
        "SELECT borough, MEASURE(bikes_available) AS bikes_available, MEASURE(docks_available) AS docks_available, "
        "MEASURE(empty_stations) AS empty_stations, MEASURE(full_stations) AS full_stations "
        "FROM fleet_status GROUP BY 1 ORDER BY 1",
    ),
    (
        "Availability by borough, all history (Executive Summary bar chart, no date filter)",
        "SELECT stations.borough, MEASURE(station_hourly.availability_rate) AS availability_rate, "
        "MEASURE(station_hourly.empty_share) AS empty_share, MEASURE(station_hourly.full_share) AS full_share "
        "FROM station_hourly CROSS JOIN stations GROUP BY 1 ORDER BY 1",
    ),
    (
        "Executive Summary cards, all history",
        "SELECT MEASURE(availability_rate) AS availability_rate, MEASURE(bikes_added) AS bikes_added "
        "FROM station_hourly",
    ),
]


def main() -> int:
    """Query Cube's SQL API and print each result table."""
    conninfo = psycopg.conninfo.make_conninfo(
        host=os.environ.get("CUBE_HOST", "localhost"),
        port=os.environ.get("CUBE_SQL_PORT", "15432"),
        user=os.environ.get("CUBEJS_SQL_USER", "dockline"),
        password=os.environ["CUBEJS_SQL_PASSWORD"],
        dbname="db",
    )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        for title, sql in QUERIES:
            cursor = conn.execute(sql)
            names = [column.name for column in cursor.description or []]
            print(f"\n{title}")
            print("  " + " | ".join(names))
            for row in cursor.fetchall():
                print(
                    "  "
                    + " | ".join(
                        f"{value:.4f}" if isinstance(value, float) else str(value) for value in row
                    )
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
