"""The approval gate: policy, interruption, rejection, and cross-process resume."""

import json

import pytest
from agents import Agent, Runner
from agents.run_state import RunState
from agents.testing import assistant_message, function_call

from ch3 import payments
from ch3.approvals import ScriptedReviewer, pending_arguments, run_with_approvals
from ch3.deps import RunDeps
from ch3.refund_tools import RefundResult, execute_refund
from tests.conftest import refund_fields, scripted, tool_call_then_message


def refund_agent(model) -> Agent[RunDeps]:
    return Agent(name="refund-agent", instructions="x", tools=[execute_refund], model=model)


async def test_small_refund_flows_without_an_interruption(deps):
    model = tool_call_then_message("execute_refund", refund_fields(amount_cents=500))
    result = await Runner.run(refund_agent(model), "refund", context=deps)
    assert result.interruptions == []
    assert payments.count_refunds() == 1
    output = next(i.output for i in result.new_items if i.type == "tool_call_output_item")
    assert isinstance(output, RefundResult) and output.amount_cents == 500
    model.assert_complete()


async def test_large_refund_stops_with_one_interruption_and_does_not_run(deps):
    model = tool_call_then_message("execute_refund", refund_fields(amount_cents=21_450))
    result = await Runner.run(refund_agent(model), "refund", context=deps)
    assert len(result.interruptions) == 1
    item = result.interruptions[0]
    assert item.name == "execute_refund"
    assert pending_arguments(item)["amount_cents"] == 21_450
    assert payments.count_refunds() == 0
    assert model.remaining_steps == 1


@pytest.mark.parametrize("cents, interrupts", [(500, False), (10_000, False), (10_001, True), (21_450, True)])
async def test_policy_threshold_is_above_one_hundred_dollars(deps, cents, interrupts):
    model = tool_call_then_message("execute_refund", refund_fields(amount_cents=cents))
    result = await Runner.run(refund_agent(model), "refund", context=deps)
    assert bool(result.interruptions) is interrupts


async def test_rejection_message_reaches_the_model_and_the_tool_never_runs(deps):
    model = tool_call_then_message(
        "execute_refund", refund_fields(), message="The reviewer declined the refund."
    )
    reviewer = ScriptedReviewer(approve=False, reason="Above the tier limit; explain, do not retry.")
    result = await run_with_approvals(refund_agent(model), "refund", deps, reviewer)
    assert result.final_output == "The reviewer declined the refund."
    assert payments.count_refunds() == 0
    assert len(reviewer.seen) == 1
    resumed_input = model.calls[1].input
    outputs = [i for i in resumed_input if isinstance(i, dict) and i.get("type") == "function_call_output"]
    assert outputs[0]["output"] == "Above the tier limit; explain, do not retry."
    model.assert_complete()


async def test_approval_runs_the_tool_under_the_context_key(deps):
    model = tool_call_then_message("execute_refund", refund_fields(), message="Issued.")
    result = await run_with_approvals(refund_agent(model), "refund", deps, ScriptedReviewer(approve=True))
    assert result.final_output == "Issued."
    row = payments.db.execute("SELECT idempotency_key, actor_id FROM refunds").fetchone()
    assert row == (deps.idempotency_key, deps.actor_id)


async def test_state_round_trips_through_a_string_with_a_context_override(deps):
    first = scripted([function_call("execute_refund", refund_fields(), call_id="call_1")])
    agent = refund_agent(first)
    paused = await Runner.run(agent, "refund", context=deps)
    blob = paused.to_state().to_string()
    assert json.loads(blob)

    second = scripted([assistant_message("Issued after approval.")])
    agent.model = second
    rebuilt = await RunState.from_string(agent, blob, context_override=deps)
    for item in rebuilt.get_interruptions():
        rebuilt.approve(item)
    result = await Runner.run(agent, rebuilt)
    assert result.final_output == "Issued after approval."
    output = next(i.output for i in result.new_items if i.type == "tool_call_output_item")
    assert isinstance(output, RefundResult) and output.status == "issued"
    stored = payments.db.execute("SELECT idempotency_key FROM refunds").fetchone()
    assert stored == (deps.idempotency_key,)


async def test_resuming_without_the_override_hands_the_tool_a_dict_and_fails_closed(deps):
    first = scripted([function_call("execute_refund", refund_fields(), call_id="call_1")])
    agent = refund_agent(first)
    paused = await Runner.run(agent, "refund", context=deps)
    blob = paused.to_state().to_string()
    agent.model = scripted([assistant_message("Something went wrong.")])
    rebuilt = await RunState.from_string(agent, blob)
    for item in rebuilt.get_interruptions():
        rebuilt.approve(item)
    result = await Runner.run(agent, rebuilt)
    output = next(i.output for i in result.new_items if i.type == "tool_call_output_item")
    assert not isinstance(output, RefundResult)
    assert payments.count_refunds() == 0
