"""Run both suites, four trials a task, and print what the run established.

python -m examples.suite_run --scripted
python -m examples.suite_run            (live model, needs OPENAI_API_KEY)
python -m examples.suite_run --judge    (live, with the groundedness judge)
"""

from __future__ import annotations

import asyncio
import sys

from chapter7.graders import grade_suite, grade_trial
from chapter7.judge import grade_groundedness
from chapter7.metrics import SuiteResult, summarize
from chapter7.models import PRICES_AS_OF
from chapter7.reviewer import build_reviewer
from chapter7.runner import run_suite
from chapter7.tasks import load_tasks
from examples.scripted import scripted_reviewer

K = 4


async def run_profile(profile: str | None, use_judge: bool = False) -> SuiteResult:
    """A full run. A profile name runs scripted. None runs the live reviewer."""
    tasks = load_tasks()
    make_agent = scripted_reviewer(profile) if profile else build_reviewer
    trials = await run_suite(make_agent, tasks, K)
    if not use_judge:
        grades = grade_suite(tasks, trials)
    else:
        by_id = {task.task_id: task for task in tasks}
        verdicts = await asyncio.gather(
            *[
                grade_groundedness(
                    t.final_state["rationale"], t.final_state["cited_clauses"]
                )
                for t in trials
            ]
        )
        grades = [
            grade_trial(by_id[t.task_id], t, grounded)
            for t, grounded in zip(trials, verdicts, strict=True)
        ]
    return summarize(profile or "live", tasks, trials, grades, K)


def report(run: SuiteResult) -> list[str]:
    mean, standard_error = run.golden_score
    passed = sum(run.golden.values())
    lines = [
        f"run: {run.run_id}, {K} trials a task",
        f"golden suite, single trial: {run.single_trial_rate:.1%} of trials passed",
        (
            f"golden suite, pass^{K}: {passed} of {len(run.golden)} tasks "
            f"({mean:.1%}, standard error {standard_error:.1%})"
        ),
        f"abuse suite, pass^{K}: {8 - len(run.abuse_failures)} of 8 cases held",
        f"cost per review: ${run.cost_per_task:.4f} (prices as of {PRICES_AS_OF})",
    ]
    for task_id, failures in sorted(run.failures.items()):
        lines.append(f"  {task_id}: {', '.join(failures)}")
    return lines


async def main(scripted_run: bool = True, use_judge: bool = False) -> SuiteResult:
    run = await run_profile("baseline" if scripted_run else None, use_judge)
    print("\n".join(report(run)))
    if not scripted_run:
        print(
            f"latency per review: p50 {run.seconds_p50:.1f}s, p95 {run.seconds_p95:.1f}s"
        )
    return run


if __name__ == "__main__":
    asyncio.run(main("--scripted" in sys.argv, "--judge" in sys.argv))
