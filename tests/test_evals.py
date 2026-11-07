"""The Ask the Data eval set and its recorded run meet the Phase 5 thresholds."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_eval_set_has_40_cases_with_unique_ids() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "evals" / "ask_the_data.jsonl").read_text().splitlines()
    ]
    assert len(cases) == 40
    assert len({case["id"] for case in cases}) == 40
    assert any(not case["supported"] for case in cases)


def test_replayed_eval_meets_thresholds() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "evals" / "run_evals.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
