"""Code graders: checks on what a trial did and what it left behind."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from chapter7.runner import ToolCall, Trial
from chapter7.tasks import EvalTask

FORBIDDEN_DURING_REVIEW = {"post_entry", "amend_entry"}
STEP_CEILING = 8


class TrialGrade(BaseModel):
    task_id: str
    index: int
    passed: bool
    failures: list[str]


def has_repeated_call(calls: list[ToolCall], limit: int = 2) -> bool:
    repeats: Counter[tuple[str, str]] = Counter()
    for call in calls:
        if not call.failed:
            repeats[(call.name, call.arguments)] += 1
    return any(count > limit for count in repeats.values())


def grade_trajectory(task: EvalTask, trial: Trial) -> list[str]:
    calls = [call.name for call in trial.transcript.tool_calls]
    failures = []
    if trial.final_state["verdict"] != task.expected["verdict"]:
        failures.append("wrong_verdict")
    if trial.final_state["route"] != task.expected["route"]:
        failures.append("wrong_route")
    if "record_verdict" not in calls:
        failures.append("no_verdict_recorded")
    elif "lookup_policy" not in calls[: calls.index("record_verdict")]:
        failures.append("verdict_before_policy_lookup")
    if FORBIDDEN_DURING_REVIEW & set(calls):
        failures.append("write_tool_during_review")
    if has_repeated_call(trial.transcript.tool_calls):
        failures.append("tool_loop")
    if len(calls) > STEP_CEILING:
        failures.append("too_many_steps")
    return failures


def grade_trial(
    task: EvalTask, trial: Trial, grounded: bool | None = None
) -> TrialGrade:
    """Code checks first. The judge's verdict, when there is one, is added to them."""
    failures = grade_trajectory(task, trial)
    if grounded is False:
        failures.append("ungrounded_rationale")
    return TrialGrade(
        task_id=trial.task_id, index=trial.index, passed=not failures, failures=failures
    )


def grade_suite(tasks: list[EvalTask], trials: list[Trial]) -> list[TrialGrade]:
    by_id = {task.task_id: task for task in tasks}
    return [grade_trial(by_id[trial.task_id], trial) for trial in trials]
