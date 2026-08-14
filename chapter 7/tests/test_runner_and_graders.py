from __future__ import annotations

import pytest

from chapter7.dataset import abuse_tasks, golden_tasks, load_tasks
from chapter7.environment import provision, teardown
from chapter7.graders import grade_suite, grade_trajectory, grade_trial
from chapter7.live import ReviewOutcome, build_compliance_agent
from chapter7.reviewer import ComplianceReviewer, UnsafeComplianceReviewer
from chapter7.runner import run_suite, run_trial


@pytest.mark.asyncio
async def test_trial_records_world_state_and_policy_first_trajectory() -> None:
    task = golden_tasks()[16]
    trial = await run_trial(ComplianceReviewer, task, 0)
    names = [call.name for call in trial.transcript.tool_calls]
    assert trial.final_state == task.expected
    assert names == [
        "lookup_policy",
        "inspect_supporting_documentation",
        "record_verdict",
    ]
    assert grade_trial(task, trial).passed is True


@pytest.mark.asyncio
async def test_each_trial_gets_an_isolated_environment() -> None:
    task = golden_tasks()[0]
    trials = await run_suite([task], k=4)
    trials[0].final_state["verdict"] = "mutated"
    assert [trial.final_state["verdict"] for trial in trials[1:]] == [
        "approve",
        "approve",
        "approve",
    ]


@pytest.mark.asyncio
async def test_complete_offline_suite_passes_four_trials_per_task() -> None:
    tasks = load_tasks()
    trials = await run_suite(tasks, k=4)
    grades = grade_suite(tasks, trials)
    assert len(trials) == 252
    assert all(grade.passed for grade in grades)


@pytest.mark.asyncio
async def test_unsafe_candidate_fails_abuse_outcome_and_write_tool_checks() -> None:
    task = abuse_tasks()[0]
    trial = await run_trial(UnsafeComplianceReviewer, task, 0)
    failures = grade_trajectory(task, trial)
    assert "wrong_verdict" in failures
    assert "write_tool_during_review" in failures
    assert "no_verdict_recorded" in failures


@pytest.mark.asyncio
async def test_memory_poisoning_is_ignored_by_safe_reviewer() -> None:
    task = abuse_tasks()[2]
    trial = await run_trial(ComplianceReviewer, task, 0)
    assert trial.final_state == task.expected
    assert grade_trial(task, trial).passed


@pytest.mark.asyncio
async def test_live_agents_sdk_target_is_wired_without_calling_the_api() -> None:
    task = golden_tasks()[0]
    environment = await provision(task)
    try:
        agent, calls = build_compliance_agent(environment)
        assert agent.name == "compliance_review_evaluation_target"
        assert [tool.name for tool in agent.tools] == [
            "lookup_policy",
            "inspect_supporting_documentation",
            "record_verdict",
        ]
        assert agent.output_type is ReviewOutcome
        assert calls == []
    finally:
        await teardown(environment)
