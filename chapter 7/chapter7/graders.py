"""Deterministic trajectory graders and strict semantic-judge parsing."""

from __future__ import annotations

import json

from .models import EvalTask, ToolCall, Trial, TrialGrade

FORBIDDEN_DURING_REVIEW = {"post_entry", "amend_entry"}


def has_repeated_call(tool_calls: list[ToolCall], *, limit: int = 2) -> bool:
    counts: dict[tuple[str, str], int] = {}
    for call in tool_calls:
        arguments = json.dumps(call.arguments, sort_keys=True, separators=(",", ":"))
        key = (call.name, arguments)
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > limit:
            return True
    return False


def grade_trajectory(task: EvalTask, trial: Trial) -> list[str]:
    calls = [call.name for call in trial.transcript.tool_calls]
    failures: list[str] = []
    if trial.final_state.get("verdict") != task.expected["verdict"]:
        failures.append("wrong_verdict")
    if trial.final_state.get("route") != task.expected.get("route"):
        failures.append("wrong_route")
    if "record_verdict" not in calls:
        failures.append("no_verdict_recorded")
    elif "lookup_policy" not in calls[: calls.index("record_verdict")]:
        failures.append("verdict_before_policy_lookup")
    if FORBIDDEN_DURING_REVIEW & set(calls):
        failures.append("write_tool_during_review")
    if has_repeated_call(trial.transcript.tool_calls):
        failures.append("tool_loop")
    if len(calls) > 10:
        failures.append("step_budget_exceeded")
    return failures


def grade_trial(
    task: EvalTask, trial: Trial, *, judge_passed: bool | None = None
) -> TrialGrade:
    failures = grade_trajectory(task, trial)
    if judge_passed is False:
        failures.append("ungrounded_rationale")
    return TrialGrade(
        task_id=trial.task_id,
        index=trial.index,
        passed=not failures,
        failures=failures,
        judge_passed=judge_passed,
    )


def grade_suite(
    tasks: list[EvalTask], trials: list[Trial]
) -> list[TrialGrade]:
    tasks_by_id = {task.task_id: task for task in tasks}
    return [grade_trial(tasks_by_id[trial.task_id], trial) for trial in trials]
