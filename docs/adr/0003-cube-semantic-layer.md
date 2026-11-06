# 0003. Cube Core as the single metrics layer

- Status: Accepted
- Date: 2026-11-06

## Context
The same metrics (fill ratio, availability rate, imbalance index, …) appear in Grafana,
Power BI, the API, the website, and LLM answers. If each surface computes them
separately, numbers drift and the LLM can invent definitions.

## Decision
Define every certified metric once in Cube Core (self-hosted, open source). The API and
Ask the Data read only through Cube's REST API. The Ask-the-Data allowlist is generated
from the Cube schema. Power BI DAX measures mirror Cube names and definitions exactly,
checked by a validation script. Grafana uses Cube-equivalent SQL against the same marts
where Cube's SQL API is not practical.

## Consequences
- One place to change a definition; the LLM physically cannot query a metric that does not exist.
- Pre-aggregations give fast responses for the API.
- Power BI and Grafana mirror rather than call Cube, so parity is enforced by tests and
  docs, not by the runtime. `docs/metrics.md` is the human-readable contract.
- Rejected: dbt Semantic Layer / MetricFlow server (hosted serving is paid), defining
  metrics only in dbt marts (no query API with access control).
