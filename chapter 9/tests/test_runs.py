"""The meter, the guardrail, and the ledger on real runner runs with scripted models."""

import pytest
from agents import Agent, Runner, trace
from agents.testing import ScriptedModel, assistant_message
from agents.testing.model import ModelStep

from chapter9.border import call_counterparty
from chapter9.budget import BudgetExceeded, RunBudget
from chapter9.meter import usage_of
from chapter9.metered import MeteredModel, step_of
from chapter9.planner import RunContext, plan_work_order
from chapter9.pricecard import UnknownPrice
from chapter9.settings import FRONTIER, IDENTITY, MODELS
from examples.common import frontier_agents, routed_agents, start
from examples.scripted import (
    MACHINE,
    TAGS,
    NordBolt,
    frontier_run,
    routed_run,
    stuck_run,
)


async def run(scripts, budget, guarded=True, routed=False):
    card, ledger = start()
    if routed:
        agents = routed_agents(*scripts, card, budget)
    else:
        agents = frontier_agents(*scripts, card, budget, guarded)
    order, trace_id = await plan_work_order(
        MACHINE, agents, RunContext(budget), TAGS
    )
    return order, ledger.runs[trace_id], ledger


async def test_every_model_call_is_priced_and_labeled_with_its_step():
    budget = RunBudget(1.00)
    order, record, _ = await run(frontier_run(), budget, guarded=False)
    assert order.parts == ["BRG-6204"]
    assert [call.step for call in record.model_calls] == [
        "plan",
        "read",
        "read",
        "read",
        "read",
        "draft",
    ]
    assert record.model_usd == pytest.approx(0.224)
    assert budget.spent_usd == pytest.approx(record.model_usd)
    assert record.turns == 6


async def test_the_ledger_stamps_identity_and_flags_the_repeat():
    _, record, _ = await run(frontier_run(), RunBudget(1.00), guarded=False)
    assert record.identity == {**IDENTITY, **TAGS}
    assert record.repeats == 1
    assert record.tool_usd == pytest.approx(0.08)


async def test_each_step_goes_to_the_model_chosen_for_it():
    budget = RunBudget(1.00)
    _, record, _ = await run(routed_run(), budget, routed=True)
    used = {(call.step, call.model) for call in record.model_calls}
    assert used == {(step, MODELS[step]) for step in ("plan", "read", "draft")}
    assert record.model_usd == pytest.approx(0.05048)
    assert budget.spent_usd == pytest.approx(record.model_usd + record.tool_usd)


async def test_a_repeated_call_is_refused_and_costs_no_fee():
    budget = RunBudget(0.20, model_calls=8, tool_calls=8)
    with pytest.raises(BudgetExceeded) as stop:
        await run(stuck_run(), budget)
    assert stop.value.reason == "run budget exhausted"
    assert budget.spent_usd <= budget.limit_usd


async def test_the_refused_calls_are_on_the_ledger_with_no_fee():
    card, ledger = start()
    budget = RunBudget(0.20, model_calls=8, tool_calls=8)
    agents = frontier_agents(*stuck_run(), card, budget, guarded=True)
    with pytest.raises(BudgetExceeded):
        await plan_work_order(MACHINE, agents, RunContext(budget), TAGS)
    record = list(ledger.runs.values())[-1]
    refused = [call for call in record.tool_calls if call.refused]
    assert len(refused) == 2 and all(call.fee_usd == 0 for call in refused)
    assert budget.spent_usd == pytest.approx(record.model_usd + record.tool_usd)


async def test_a_stop_at_a_tool_call_reaches_the_caller_as_a_budget_stop():
    card, ledger = start()
    budget = RunBudget(1.00, tool_calls=1)
    agents = frontier_agents(*frontier_run(), card, budget, guarded=True)
    with pytest.raises(BudgetExceeded, match="no tool calls left") as stop:
        await plan_work_order(MACHINE, agents, RunContext(budget), TAGS)
    assert stop.value.wanted == pytest.approx(0.01)
    record = list(ledger.runs.values())[-1]
    stopped = [call for call in record.tool_calls if call.stopped]
    assert len(stopped) == 1 and stopped[0].fee_usd == 0
    assert not stopped[0].failed
    assert budget.spent_usd == pytest.approx(record.model_usd + record.tool_usd)


async def test_a_dollar_stop_at_a_tool_call_spends_nothing_more():
    card, _ = start()
    budget = RunBudget(0.045, first_call_usd=0.02)
    agents = frontier_agents(*frontier_run(), card, budget, guarded=True)
    with pytest.raises(BudgetExceeded, match="run budget exhausted"):
        await plan_work_order(MACHINE, agents, RunContext(budget), TAGS)
    assert budget.spent_usd <= budget.limit_usd


async def test_the_call_count_stops_a_loop_that_the_dollars_would_allow():
    budget = RunBudget(5.00, model_calls=4, tool_calls=8)
    with pytest.raises(BudgetExceeded, match="no model calls left"):
        await run(stuck_run(), budget)


async def test_an_unpriced_model_fails_before_the_provider_is_called():
    card, _ = start()
    inner = ScriptedModel([ModelStep(output=[assistant_message("hi")])])
    model = MeteredModel(inner, "gpt-7-preview", card, RunBudget(1.00))
    with pytest.raises(UnknownPrice):
        await Runner.run(Agent(name="a", model=model), "hello")
    assert inner.calls == ()


async def test_a_failed_call_releases_its_reservation():
    card, _ = start()
    budget = RunBudget(1.00)
    inner = ScriptedModel([ModelStep(error=RuntimeError("provider down"))])
    model = MeteredModel(inner, FRONTIER, card, budget)
    with pytest.raises(RuntimeError):
        await Runner.run(Agent(name="a", model=model), "hello")
    assert budget.reserved_usd == pytest.approx(0.0)
    assert budget.spent_usd == 0.0


async def test_a_streamed_call_is_metered_too():
    card, ledger = start()
    budget = RunBudget(1.00)
    step = ModelStep(
        output=[assistant_message("hi")], usage=usage_of(1_000, 100)
    )
    model = MeteredModel(ScriptedModel([step]), FRONTIER, card, budget)
    with trace("stream", metadata=TAGS) as seen:
        stream = Runner.run_streamed(Agent(name="a", model=model), "hello")
        async for _ in stream.stream_events():
            pass
    assert budget.spent_usd == pytest.approx(0.003)
    assert ledger.runs[seen.trace_id].model_usd == pytest.approx(0.003)


def test_a_call_is_planning_until_a_tool_result_arrives():
    assert step_of("diagnose press-07") == "plan"
    assert step_of([{"type": "message"}]) == "plan"
    assert step_of([{"type": "function_call_output"}]) == "read"


async def test_the_outcome_is_joined_by_the_approval_flow():
    _, record, ledger = await run(frontier_run(), RunBudget(1.00), guarded=False)
    ledger.label(record.trace_id, "approved", "WO-2R0412", review_minutes=2.0)
    assert (record.outcome, record.outcome_ref) == ("approved", "WO-2R0412")
    with pytest.raises(ValueError):
        ledger.label(record.trace_id, "looks fine", "WO-1", 1.0)


async def test_a_run_without_identity_is_marked_and_not_dropped():
    card, ledger = start()
    model = MeteredModel(
        ScriptedModel([ModelStep(output=[assistant_message("hi")])]),
        FRONTIER,
        card,
        RunBudget(1.00),
    )
    with trace("untagged") as seen:
        await Runner.run(Agent(name="a", model=model), "hello")
    assert ledger.runs[seen.trace_id].identity["plant"] == "unattributed"


async def test_the_border_span_records_the_call_and_the_quoted_cost():
    _, ledger = start()
    supplier = NordBolt()
    with trace("quote", metadata=TAGS) as seen:
        reply = await call_counterparty(
            supplier, {"skill": "quote"}, "WO-2R0412"
        )
    border = ledger.runs[seen.trace_id].borders[0]
    assert reply.status == "completed" and border["attempts"] == 2
    assert border["quoted_cost_usd"] == 0.04
    assert supplier.calls[-1] == {"x-correlation-id": "WO-2R0412"}
