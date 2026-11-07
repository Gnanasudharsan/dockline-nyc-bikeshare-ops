# 0008. Schedule station_status polls from the feed's clock

- Status: Accepted
- Date: 2026-11-07

## Context
The first 15-minute acceptance run polled on a fixed 60 s timer. The feed publishes a
new version about once a minute, and our timer settled about 1 s *before* each
publish. Twice in 15 minutes the CDN still served the previous version, so that poll
added nothing and the next one carried two minutes of reports. No data was lost, but a
fixed timer can phase-lock against the publisher indefinitely.

## Decision
Use the feed's own validity window. After each poll:
- if the feed returned a new version, wait until `last_updated + ttl + 5 s`;
- if it returned the same version as last time, retry after the 15 s minimum;
- always clamp the wait to [15 s, 300 s].

## Consequences
- Polls track the publisher, so each minute's version is picked up promptly.
- Never more often than every 15 s, and only when the data is overdue, which is
  consistent with the GBFS ttl contract.
- If our clock and the feed's clock disagree badly, the clamp limits the damage.
