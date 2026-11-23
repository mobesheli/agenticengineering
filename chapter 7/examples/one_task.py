"""One task, four trials: the trajectory of one trial, then all four verdicts.

python -m examples.one_task --scripted
"""

from __future__ import annotations

import asyncio
import sys

from chapter7.graders import grade_trial
from chapter7.reviewer import build_reviewer
from chapter7.runner import run_suite
from chapter7.tasks import task_by_id
from examples.scripted import scripted_reviewer


async def main(scripted_run: bool = True, task_id: str = "je-split-02") -> list:
    task = task_by_id(task_id)
    make_agent = scripted_reviewer("baseline") if scripted_run else build_reviewer
    trials = await run_suite(make_agent, [task], k=4)
    grades = [grade_trial(task, trial) for trial in trials]
    print(f"{task.task_id}: expected {task.expected['verdict']}")
    print("trial 1 trajectory:")
    for call in trials[0].transcript.tool_calls:
        print(f"  {call.name}")
    print("trial  recorded  result")
    for trial, grade in zip(trials, grades, strict=True):
        result = "pass" if grade.passed else "fail: " + ", ".join(grade.failures)
        print(f"{trial.index + 1:5d}  {trial.final_state['verdict']!s:8}  {result}")
    passes = [grade.passed for grade in grades]
    print(
        f"pass@4: {'yes' if any(passes) else 'no'}   pass^4: {'yes' if all(passes) else 'no'}"
    )
    return grades


if __name__ == "__main__":
    asyncio.run(main(scripted_run="--scripted" in sys.argv))
