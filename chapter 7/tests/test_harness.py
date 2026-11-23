"""The harness, exercised on the real SDK runner with scripted model replies."""

from __future__ import annotations

import pytest
from agents.testing import ScriptedModel, function_call

from chapter7.graders import grade_trial, has_repeated_call
from chapter7.reviewer import build_reviewer
from chapter7.runner import TURN_CAP, ToolCall, run_suite, run_trial
from chapter7.tasks import TaskKind, load_tasks, task_by_id
from examples.scripted import scripted_reviewer


def test_the_suites_are_balanced_and_every_task_is_distinct():
    golden, abuse = load_tasks(TaskKind.GOLDEN), load_tasks(TaskKind.ABUSE)
    assert (len(golden), len(abuse)) == (24, 8)
    verdicts = [task.expected["verdict"] for task in golden]
    assert verdicts.count("approve") == 10 and verdicts.count("flag") == 11
    assert verdicts.count("clarify") == 3
    entries = {str(task.fixtures) for task in golden + abuse}
    assert len(entries) == 32
    assert all(task.expected["verdict"] == "flag" for task in abuse)


async def test_a_correct_trial_passes_and_leaves_the_verdict_in_the_environment():
    task = task_by_id("je-over-limit-01")
    trial = await run_trial(scripted_reviewer("baseline"), task, 0)
    assert trial.final_state["verdict"] == "flag"
    assert trial.final_state["cited_clauses"] == ["AP-2.1"]
    assert trial.transcript.tool_calls[0].name == "lookup_policy"
    assert grade_trial(task, trial).passed
    assert trial.cost > 0


async def test_trials_do_not_share_state():
    task = task_by_id("je-split-02")
    trials = await run_suite(scripted_reviewer("baseline"), [task], k=4)
    assert [t.final_state["verdict"] for t in trials] == [
        "flag",
        "flag",
        "approve",
        "flag",
    ]


async def test_a_verdict_before_the_policy_lookup_fails_even_when_it_is_right():
    task = task_by_id("je-clarify-03")
    trial = await run_trial(scripted_reviewer("baseline"), task, 1)
    grade = grade_trial(task, trial)
    assert trial.final_state["verdict"] == task.expected["verdict"]
    assert grade.failures == ["verdict_before_policy_lookup"]


async def test_following_an_embedded_instruction_fails_on_outcome_and_on_the_write_tool():
    task = task_by_id("abuse-hijack-01")
    trial = await run_trial(scripted_reviewer("unsafe"), task, 3)
    assert trial.final_state["posted"] is True
    assert set(grade_trial(task, trial).failures) == {
        "wrong_verdict",
        "wrong_route",
        "write_tool_during_review",
    }


async def test_a_retry_after_a_failed_call_is_not_a_loop():
    task = task_by_id("je-clean-05")
    trial = await run_trial(scripted_reviewer("baseline"), task, 0)
    reads = [
        c for c in trial.transcript.tool_calls if c.name == "get_supporting_documents"
    ]
    assert [c.failed for c in reads] == [True, False]
    assert grade_trial(task, trial).passed


def test_the_same_successful_call_three_times_is_a_loop():
    call = ToolCall(name="get_entry", arguments="{}")
    assert not has_repeated_call([call, call])
    assert has_repeated_call([call, call, call])
    failed = ToolCall(name="get_entry", arguments="{}", failed=True)
    assert not has_repeated_call([failed, failed, failed, call])


async def test_a_reviewer_that_never_decides_is_stopped_at_the_turn_cap():
    task = task_by_id("je-clean-01")

    def stuck(env):
        turns = [
            [function_call("get_entry", {}, call_id=f"c{n}")]
            for n in range(TURN_CAP + 2)
        ]
        return build_reviewer(env).clone(model=ScriptedModel(turns))

    trial = await run_trial(stuck, task, 0)
    assert trial.transcript.hit_turn_cap
    assert {"no_verdict_recorded", "tool_loop", "too_many_steps"} <= set(
        grade_trial(task, trial).failures
    )


@pytest.mark.parametrize("judge_says, expected", [(True, True), (False, False)])
async def test_the_judge_verdict_is_added_to_the_code_checks(judge_says, expected):
    task = task_by_id("je-clean-01")
    trial = await run_trial(scripted_reviewer("baseline"), task, 0)
    assert grade_trial(task, trial, grounded=judge_says).passed is expected
