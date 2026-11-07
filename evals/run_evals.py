"""Score Ask the Data on evals/ask_the_data.jsonl.

Each case runs through the real pipeline functions: input cleaning, the injection
screen, the planner model, schema parsing, and strict validation. A case is correct when:

* answerable: the validated plan uses the expected topic, measures, dimensions, filters,
  and (when given) time range and granularity;
* unanswerable: the pipeline refuses (injection screen, planner refusal, or validation).

Modes:
* ``--live`` calls the configured LLM and records each raw plan into
  ``evals/cassettes/<provider>.json``, keyed by question and a hash of the planner
  prompt. ``--execute`` also runs every validated query on Cube.
* default (replay) reads the cassette: deterministic, no API key, used in CI. If the
  planner prompt changed since recording, replay fails and asks for a live run.

Thresholds (CLAUDE.md, Phase 5): ≥ 85% of answerable cases, 100% of refusals.

Usage: ``uv run python evals/run_evals.py [--live] [--execute] [--provider groq]``.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from dockline_api.ask import (
    clean_question,
    looks_like_injection,
    planner_prompt,
    planner_user_message,
)
from dockline_api.config import Settings
from dockline_api.cube import CubeClient, CubeError
from dockline_api.llm import LLMError, build_llm
from dockline_api.query import PlanError, ValidatedQuery, parse_plan, validate_plan

EVALS_DIR = Path(__file__).resolve().parent
CASES_PATH = EVALS_DIR / "ask_the_data.jsonl"
ANSWERABLE_THRESHOLD = 0.85
REFUSAL_THRESHOLD = 1.0


@dataclass
class Outcome:
    """Result of one case."""

    case_id: str
    supported_expected: bool
    correct: bool
    detail: str


def prompt_hash() -> str:
    """Identify the planner prompt version a cassette was recorded with."""
    return hashlib.sha256(planner_prompt().encode()).hexdigest()[:16]


def load_cases() -> list[dict[str, Any]]:
    """Read the JSONL eval set."""
    return [json.loads(line) for line in CASES_PATH.read_text().splitlines() if line.strip()]


def normalized_filters(items: list[Any]) -> set[tuple[str, tuple[str, ...]]]:
    """Turn filters into comparable (member, sorted lower-case values) pairs."""
    result = set()
    for item in items:
        member = item["member"] if isinstance(item, dict) else item.member
        values = item["values"] if isinstance(item, dict) else item.values
        result.add((member, tuple(sorted(v.lower() for v in values))))
    return result


def score_answerable(case: dict[str, Any], validated: ValidatedQuery) -> tuple[bool, str]:
    """Compare a validated plan with the expected one."""
    problems = []
    if validated.topic != case["topic"]:
        problems.append(f"topic {validated.topic} != {case['topic']}")
    options = case.get("measures_options") or [case["measures"]]
    if set(validated.measures) not in [set(option) for option in options]:
        problems.append(f"measures {validated.measures} != {options}")
    if set(validated.dimensions) != set(case["dimensions"]):
        problems.append(f"dimensions {validated.dimensions} != {case['dimensions']}")
    if normalized_filters(validated.filters) != normalized_filters(case["filters"]):
        problems.append(
            f"filters {[f.model_dump() for f in validated.filters]} != {case['filters']}"
        )
    if case.get("time_range", "any") != "any" and validated.time_range != case["time_range"]:
        problems.append(f"time_range {validated.time_range!r} != {case['time_range']!r}")
    if "granularity" in case and validated.granularity != case["granularity"]:
        problems.append(f"granularity {validated.granularity!r} != {case['granularity']!r}")
    return not problems, "; ".join(problems) or "ok"


class CassetteLLM:
    """Replays recorded planner outputs."""

    def __init__(self, path: Path) -> None:
        """Load a cassette and check it matches the current planner prompt."""
        if not path.exists():
            raise SystemExit(f"No cassette at {path}. Run with --live first.")
        data = json.loads(path.read_text())
        if data["prompt_hash"] != prompt_hash():
            raise SystemExit(
                f"Cassette {path.name} was recorded with planner prompt {data['prompt_hash']}, "
                f"but the prompt is now {prompt_hash()}. Re-record with --live."
            )
        self.plans: dict[str, Any] = data["plans"]
        self.model = data.get("model", "")

    async def plan(self, question: str) -> dict[str, Any]:
        """Return the recorded raw plan."""
        if question not in self.plans:
            raise SystemExit(f"Question not in cassette: {question!r}. Re-record with --live.")
        recorded = self.plans[question]
        if "error" in recorded:
            raise LLMError(recorded["error"])
        plan: dict[str, Any] = recorded
        return plan


async def run(args: argparse.Namespace) -> int:
    """Score every case; return the process exit code."""
    cases = load_cases()
    provider = args.provider or os.environ.get("LLM_PROVIDER", "groq")
    cassette_path = EVALS_DIR / "cassettes" / f"{provider}.json"
    recorded: dict[str, Any] = {}
    outcomes: list[Outcome] = []
    executed = 0

    async with httpx.AsyncClient(timeout=60) as http:
        live_llm = None
        cube = None
        model_name = ""
        if args.live or args.execute:
            settings = Settings(llm_provider=provider)
            if args.live:
                live_llm = build_llm(settings, http)
                model_name = getattr(live_llm, "model", provider)
            if args.execute:
                cube = CubeClient(
                    http, settings.cube_api_url, settings.cubejs_api_secret.get_secret_value()
                )
        replay = None if args.live else CassetteLLM(cassette_path)

        for case in cases:
            question = clean_question(case["question"], 300)
            refused, validated, detail = False, None, ""
            if looks_like_injection(question):
                refused, detail = True, "injection screen"
            else:
                try:
                    if live_llm is not None:
                        try:
                            raw = await live_llm.complete_json(
                                planner_prompt(), planner_user_message(question)
                            )
                            recorded[question] = raw
                        except LLMError as error:
                            recorded[question] = {"error": str(error)}
                            raise
                    elif replay is not None:
                        raw = await replay.plan(question)
                    else:
                        raise SystemExit("no planner available")
                    plan = parse_plan(raw)
                    if not plan.supported:
                        refused, detail = True, f"planner refused: {plan.refusal_reason}"
                    else:
                        validated = validate_plan(plan)
                except PlanError as error:
                    refused, detail = True, f"validation: {error}"
                except LLMError as error:
                    detail = f"LLM error: {error}"

            if case["supported"]:
                if validated is None:
                    outcomes.append(Outcome(case["id"], True, False, detail or "refused"))
                    continue
                correct, detail = score_answerable(case, validated)
                if correct and cube is not None:
                    try:
                        await cube.load(validated.cube_query)
                        executed += 1
                    except CubeError as error:
                        correct, detail = False, f"Cube rejected the query: {error}"
                outcomes.append(Outcome(case["id"], True, correct, detail))
            else:
                outcomes.append(
                    Outcome(
                        case["id"],
                        False,
                        refused,
                        detail if refused else "answered instead of refusing",
                    )
                )

    if args.live:
        cassette_path.parent.mkdir(parents=True, exist_ok=True)
        cassette_path.write_text(
            json.dumps(
                {
                    "provider": provider,
                    "model": model_name,
                    "prompt_hash": prompt_hash(),
                    "plans": recorded,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    answerable = [o for o in outcomes if o.supported_expected]
    refusals = [o for o in outcomes if not o.supported_expected]
    answerable_rate = sum(o.correct for o in answerable) / len(answerable)
    refusal_rate = sum(o.correct for o in refusals) / len(refusals)
    for outcome in outcomes:
        print(f"{'PASS' if outcome.correct else 'FAIL'}  {outcome.case_id:<11} {outcome.detail}")
    print(
        f"\nmode: {'live' if args.live else 'replay'} ({provider})"
        + (f", {executed} queries executed on Cube" if cube is not None else "")
    )
    answered_ok = sum(o.correct for o in answerable)
    refused_ok = sum(o.correct for o in refusals)
    print(
        f"answerable: {answered_ok}/{len(answerable)} = {answerable_rate:.1%} "
        f"(threshold {ANSWERABLE_THRESHOLD:.0%})"
    )
    print(
        f"refusals:   {refused_ok}/{len(refusals)} = {refusal_rate:.1%} "
        f"(threshold {REFUSAL_THRESHOLD:.0%})"
    )
    passed = answerable_rate >= ANSWERABLE_THRESHOLD and refusal_rate >= REFUSAL_THRESHOLD
    print("RESULT: " + ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


def main() -> int:
    """Parse arguments and run."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--live", action="store_true", help="call the LLM and re-record the cassette"
    )
    parser.add_argument("--execute", action="store_true", help="also run validated queries on Cube")
    parser.add_argument("--provider", help="gemini | groq | ollama (default: LLM_PROVIDER)")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
