"""Run the complete deterministic suite and optionally emit evidence."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .dataset import load_tasks
from .evidence import emit_evidence_pack
from .graders import grade_suite
from .metrics import build_suite_result
from .runner import run_suite


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Chapter 7 evaluation suite.")
    parser.add_argument("--trials", type=int, default=4)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    tasks = load_tasks()
    if args.live:
        from .live import LiveComplianceReviewer

        trials = await run_suite(tasks, args.trials, LiveComplianceReviewer)
    else:
        trials = await run_suite(tasks, args.trials)
    result = build_suite_result(trials, grade_suite(tasks, trials))
    if args.evidence_dir:
        emit_evidence_pack(result, args.evidence_dir)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
