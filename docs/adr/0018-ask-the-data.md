# 0018. Ask the Data: LLM plans, code validates, Cube answers

- Status: Accepted
- Date: 2026-11-07

## Context
Natural-language questions are useful, but an LLM that writes SQL can invent metrics,
read data it should not, or be steered by prompt injection. Answers must use certified
metrics (ADR 0003), never invent numbers, and run on free tiers.

## Decision
- The LLM never writes SQL or Cube queries. It returns a **small JSON plan**: a topic and
  short names from an allowlisted catalog. Code (`query.py`) validates the plan strictly
  and builds the Cube REST query. Anything outside the catalog is a refusal, not an
  error.
- **Layered injection defense:**
  1. input limits
  2. a pattern screen before any model call
  3. the question passed as quoted data with explicit instructions
  4. an output schema with no free-form fields that reach a query
  5. answers checked for grounding (every number must appear in Cube's rows), with a
     template answer as the fallback
- **Refusals** carry the reason and the nearest supported question. The question is
  chosen by index from a fixed list, so the model cannot inject text into it.
- **Every answer returns** the metrics with their certified definitions, the validated
  query, the rows, and data freshness. Users can check the number themselves.
- **Provider:** Groq free tier (`openai/gpt-oss-120b`) by default; Gemini and Ollama
  are alternatives behind the same interface. Temperature 0, JSON mode, bounded retries
  on 429.
- **Evaluation:** 40 cases scored by the real pipeline functions. Live runs are recorded
  to a cassette tied to a hash of the planner prompt. CI replays the cassette (no
  secret, deterministic) and enforces ≥ 85% answerable and 100% refusals.
- Rolling ranges ("last 7 days") are sent to Cube as "from 7 days ago to now", because
  Cube's `last 7 days` excludes today.

## Consequences
- Scope is deliberately narrow; new question types need catalog entries, which also
  means a reviewed change.
- CI cannot detect provider drift. `make eval-live` must be re-run when the model or
  prompt changes, and the prompt hash forces this.
- The free tier allows about 8,000 tokens per minute; the per-client and daily limits
  keep the public site inside it.
