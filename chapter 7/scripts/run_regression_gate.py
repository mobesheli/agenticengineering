"""Run the offline suite and return a deployment-friendly exit code."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chapter7.dataset import load_tasks
from chapter7.gates import gate
from chapter7.graders import grade_suite
from chapter7.metrics import build_suite_result
from chapter7.models import SuiteResult
from chapter7.runner import run_suite


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Chapter 7 regression gate.")
    parser.add_argument("--baseline", type=Path, default=ROOT / "data" / "baseline.json")
    parser.add_argument("--trials", type=int, default=4)
    args = parser.parse_args()
    baseline = SuiteResult.model_validate_json(args.baseline.read_text())
    tasks = load_tasks()
    trials = await run_suite(tasks, args.trials)
    current = build_suite_result(trials, grade_suite(tasks, trials))
    verdict = gate(current, baseline)
    print(json.dumps(verdict.model_dump(), indent=2))
    return 1 if verdict.status == "block" else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
