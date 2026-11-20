"""A plan is data: it can be checked before it runs and again when it changes."""

from __future__ import annotations

from pydantic import BaseModel


class PlanStep(BaseModel):
    step_id: str
    description: str
    tool: str
    writes: bool
    success_check: str


class Plan(BaseModel):
    goal: str
    steps: list[PlanStep]


def validate_plan(plan: Plan, allowed_tools: set[str], max_steps: int) -> list[str]:
    problems = [
        f"Step {step.step_id} uses a tool that is not allowed: {step.tool}"
        for step in plan.steps
        if step.tool not in allowed_tools
    ]
    if len(plan.steps) > max_steps:
        problems.append(f"{len(plan.steps)} steps; the budget is {max_steps}.")
    return problems


class ExecutionRecord(BaseModel):
    """What has already happened in this run. Appended to, never rewritten."""

    completed: dict[str, str] = {}
    replans: int = 0


def validate_revision(
    revised: Plan,
    record: ExecutionRecord,
    allowed_tools: set[str],
    max_steps: int,
    max_replans: int = 2,
) -> list[str]:
    steps_left = max_steps - len(record.completed)
    problems = validate_plan(revised, allowed_tools, steps_left)
    if record.replans >= max_replans:
        problems.append("Replan limit reached; send the case to a person.")
    problems += [
        f"Step {step.step_id} already ran; a revision may not run it again."
        for step in revised.steps
        if step.step_id in record.completed
    ]
    return problems


def writes_needing_approval(approved: Plan, revised: Plan) -> list[PlanStep]:
    """Writing steps in the revision that nobody has seen and approved yet."""
    seen = {(step.tool, step.description) for step in approved.steps if step.writes}
    return [
        step
        for step in revised.steps
        if step.writes and (step.tool, step.description) not in seen
    ]
