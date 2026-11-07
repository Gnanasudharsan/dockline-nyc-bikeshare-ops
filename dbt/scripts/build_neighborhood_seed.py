"""Build ``seeds/nyc_neighborhoods.csv`` from NYC Open Data's 2020 NTA boundaries.

The warehouse image has no PostGIS, so neighborhoods are stored as core Postgres
``polygon`` literals and matched with the ``@>`` (contains) operator. Polygons are
simplified (~20 m tolerance) to keep the seed small; stations that land just outside
every polygon (piers, shoreline) are matched to the nearest one in dbt.

Usage (from the repo root)::

    curl -sL -o /tmp/nta.geojson \
      "https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON"
    uv run --with shapely python dbt/scripts/build_neighborhood_seed.py /tmp/nta.geojson

Source: NYC Department of City Planning, "2020 Neighborhood Tabulation Areas (NTAs)",
NYC Open Data dataset 9nt8-h7nd.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from shapely.geometry import shape

TOLERANCE_DEGREES = 0.0002
OUTPUT = Path(__file__).resolve().parent.parent / "seeds" / "nyc_neighborhoods.csv"


def polygon_literal(coords: list[tuple[float, float]]) -> str:
    """Format an exterior ring as a Postgres polygon literal ``((x,y),...)``."""
    points = ",".join(f"({x:.5f},{y:.5f})" for x, y in coords[:-1])
    return f"({points})"


def main(source: Path) -> None:
    """Read the GeoJSON, simplify each NTA, and write one CSV row per polygon part."""
    features = json.loads(source.read_text())["features"]
    rows = []
    for feature in features:
        props = feature["properties"]
        geometry = shape(feature["geometry"]).simplify(TOLERANCE_DEGREES, preserve_topology=True)
        parts = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
        for index, part in enumerate(parts):
            if part.is_empty or part.area == 0:
                continue
            rows.append(
                {
                    "nta_code": props["nta2020"],
                    "nta_name": props["ntaname"],
                    "borough": props["boroname"],
                    "nta_type": props["ntatype"],
                    "part_index": index,
                    "boundary": polygon_literal(list(part.exterior.coords)),
                }
            )
    rows.sort(key=lambda row: (row["nta_code"], row["part_index"]))
    with OUTPUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} polygon parts to {OUTPUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
