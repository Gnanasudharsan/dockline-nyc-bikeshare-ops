# api

FastAPI service for the website and for people: live KPIs, a live KPI stream, live
stations for the map, the metric catalog, and **Ask the Data**. Every number comes from
Cube; the service never writes SQL. Runs on <http://localhost:8070> (`make up`).

| Endpoint | What it returns |
| --- | --- |
| `GET /health` | Liveness and a Cube round trip |
| `GET /v1/kpis/live` | Network KPIs right now (Cube `fleet_status`): bikes, docks, empty/full/starving/flooding/offline stations, fill ratio, bikes to move, data freshness |
| `GET /v1/kpis/stream` | Server-Sent Events: a `kpis` event every 10 s (same payload) |
| `GET /v1/stations/live` | Every station with position, state, bikes, docks (for the map) |
| `GET /v1/metrics` | Metrics Ask the Data can use, with definitions, and example questions |
| `POST /v1/ask` | `{"question": "..."}` → answer, metrics + definitions, the validated query, rows, data freshness |

## Ask the Data

```
question ──► input limits ──► injection screen ──► planner LLM ──► JSON plan
                                                                  │
            answer ◄── grounding check ◄── answer LLM ◄── Cube ◄──┘ strict validation
```

1. **Input limits**: at most 300 characters, printable text only. Rate limits are 6
   questions per minute per client and 500 a day for everyone, which protects the free
   LLM quota.
2. **Injection screen**: text that reads like instructions to the assistant (such as
   "ignore previous instructions" or "system prompt") or like SQL is refused before any
   model sees it.
3. **Planner**: the LLM sees the catalog (`catalog.py`) and the question, which is
   passed as quoted data. It may only return a small JSON plan: a topic, short member
   names, filters, and a time range from a fixed list.
4. **Strict validation** (`query.py`):
   - Unknown keys, members, operators, values, and ranges are rejected.
   - Filter values must come from closed lists where one exists (boroughs, states,
     weather conditions).
   - Limits are bounded.
   - Only then is a Cube REST query built.
5. **Cube** runs the query. The service signs a 5-minute JWT and uses the same metric
   definitions as Grafana and Power BI.
6. **Answer**: a second LLM call writes at most 3 sentences from the returned rows only.
   Every number in it must appear in those rows, as is, rounded, or as a percentage. If
   not, a deterministic template answer is used (`answer_source: "template"`).
7. **Refusals**: questions outside the catalog (trips, revenue, forecasts, riders, off
   topic) get a reason plus the nearest supported question. The planner points to it by
   index into a fixed list, so it can never invent the suggestion text.

Providers (`LLM_PROVIDER`, free tiers only):
- `groq` (default, `openai/gpt-oss-120b`)
- `gemini` (`gemini-2.5-flash`)
- `ollama` (local)

Calls use temperature 0 and JSON mode, and on HTTP 429 the client waits and retries a
bounded number of times.

```bash
make ask Q="Which borough has the most empty stations right now?"
```

## Evaluation

`evals/ask_the_data.jsonl` has 40 cases: 32 answerable, each with the expected plan,
and 8 that must be refused (out of scope, plus 3 injection attempts).

```bash
make eval
```
```bash
make eval-live
```

`make eval` replays the recorded live run, so it needs no API key; CI runs it. Run
`make eval-live` after changing the planner prompt or catalog. It calls the configured
LLM, runs every validated query on Cube, and re-records
`evals/cassettes/<provider>.json`. The cassette stores a hash of the planner prompt, so
replaying a stale recording fails.

Thresholds: **≥ 85% of answerable cases** and **100% of refusals**.

Latest live run (Groq `openai/gpt-oss-120b`, 2026-11-07):
- 31 of 32 answerable (96.9%)
- 8 of 8 refusals (100%)
- all 31 queries ran on Cube

Known miss: "How does rain affect availability?" is planned as a filter on rain instead
of a comparison across weather conditions.

Design notes: [ADR 0018](../docs/adr/0018-ask-the-data.md).
