# 0005. Resolve GBFS feeds via discovery, prefer v2.3

- Status: Accepted
- Date: 2026-11-06

## Context
The documented entry point `https://gbfs.citibikenyc.com/gbfs/gbfs.json` still works
(checked 2026-11-06) but returns GBFS v1.1 feed URLs hosted on `gbfs.lyft.com`. Its
`gbfs_versions.json` also advertises v2.3 at `https://gbfs.lyft.com/gbfs/2.3/bkn/gbfs.json`.
v2.3 `station_status` returns about 2,500 stations, `ttl = 60`, and includes
`vehicle_types_available` and `num_ebikes_available`. Inactive stations report
`last_reported = 86400`, a sentinel rather than a real timestamp. Hard-coding feed URLs
would break silently if the operator moves them again.

## Decision
At startup and periodically, fetch the discovery file, read `gbfs_versions`, and pick the
version in `GBFS_PREFERRED_VERSION` (default 2.3), falling back to whatever discovery
lists. Resolve `station_status`, `station_information`, and `system_information` URLs
from that version's discovery file. Poll at the feed's `ttl`. Treat implausible
`last_reported` values as "never reported".

## Consequences
- Survives URL moves without a code change; the chosen version is logged per run.
- Validation must handle the sentinel timestamp and missing optional fields.
