# 0009. Conditional requests for station_status

- Status: Accepted
- Date: 2026-11-07

## Context
After ADR 0008, the second acceptance run showed that the CDN (CloudFront) makes each
new version visible 20–35 s after its `last_updated` stamp, and the delay varies. The
poll at `last_updated + ttl + 5 s` therefore usually found the old version and
downloaded the full ~600 KB payload for nothing, about 2.7 downloads per minute. The
CDN returns an `ETag` and answers `If-None-Match` with `304 Not Modified` and an empty body.

## Decision
- Remember the `ETag` per feed URL and send it as `If-None-Match`. A 304 is recorded
  as a successful run with `ops.ingestion_runs.not_modified = true` (migration 0008).
- Keep ADR 0008's schedule. When the version is unchanged, check again after 10 s
  (down from 15 s), which is affordable because a 304 has no body.
- Rejected: estimating the CDN delay from past polls. It is more code, it drifts, and
  it still guesses wrong when the delay changes.

## Consequences
- About one full download per feed version; the extra checks are empty 304s.
- New versions land within about 10 s of reaching the CDN.
- The audit log separates "feed unchanged" (`not_modified`) from "downloaded, but no
  station had a new report" (`records_duplicate`).
