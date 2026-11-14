# Dockline snapshot data

Generated every 10 minutes by the Snapshot workflow
(`.github/workflows/snapshot.yml` on `main`). This branch is a single commit that each
run replaces; do not commit here.

| File | Contents |
| --- | --- |
| `latest.json` | The latest poll: certified network KPIs, every station's state, and the current weather |
| `history-24h.json` | 10-minute frames for the last 24 hours: each station's state (`s` starving, `b` balanced, `f` flooding, `o` offline, `-` no data) and the network KPIs |
| `daily-kpis.json` | Per New York day (last 30): sampled availability rate, empty and full station-minutes, average bikes and docks |

Metric definitions: `docs/metrics.md` on `main`. Source: the public Citi Bike GBFS feed
and Open-Meteo. Independent project. Not affiliated with Citi Bike or Lyft.
