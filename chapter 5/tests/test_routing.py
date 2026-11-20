"""Handoffs, the classifier router, its evaluation, canaries, plans, and fan-out."""

from collections import Counter

import pytest
from agents import RunConfig, Runner
from agents.testing import ScriptedModel

from chapter5 import fanout, router, routing
from chapter5.canary import pick_frontier_model
from chapter5.models import MODELS
from chapter5.planning import (
    ExecutionRecord,
    Plan,
    PlanStep,
    validate_plan,
    validate_revision,
    writes_needing_approval,
)
from chapter5.router_eval import Scored, confusion, precision_recall, threshold_report
from examples.scripted import calls, says, scripted


def one_model(*turns: list) -> RunConfig:
    return RunConfig(model=ScriptedModel(list(turns)), tracing_disabled=True)


async def test_a_dispute_is_handed_off_with_a_typed_reason():
    routing.TRANSFERS.clear()
    transfer = calls(
        "transfer_to_dispute_specialist",
        {"reason": "Charged twice by the hotel.", "transaction_reference": "txn-8841"},
    )
    run = await Runner.run(
        routing.intake_agent,
        "The hotel charged me twice.",
        run_config=one_model(transfer, says("I have opened a dispute for txn-8841.")),
    )

    assert run.last_agent.name == "dispute_specialist"
    assert routing.TRANSFERS[0].transaction_reference == "txn-8841"


async def test_a_fee_question_is_answered_by_a_function_and_intake_keeps_the_conversation():
    run = await Runner.run(
        routing.intake_agent,
        "What would 650 payments cost on premium?",
        run_config=one_model(
            calls("estimate_fees", {"tier": "premium", "payments": 650}),
            says("150 billable payments, 15.00 in fees."),
        ),
    )
    output = next(i.output for i in run.new_items if i.type == "tool_call_output_item")

    assert run.last_agent.name == "intake_agent"
    assert output == "150 billable payments at 0.10 each: 15.00"


@pytest.fixture
def routed(monkeypatch):
    def install(decision: dict) -> None:
        router.HUMAN_QUEUE.clear()
        monkeypatch.setattr(
            router, "request_router", scripted(router.request_router, says(decision))
        )
        for name, agent in router.SPECIALISTS.items():
            monkeypatch.setitem(
                router.SPECIALISTS, name, scripted(agent, says(f"{name} handled"))
            )

    return install


async def test_a_confident_decision_reaches_the_specialist(routed):
    routed({"category": "dispute", "confidence": 0.93, "reason": "Double charge."})

    outcome = await router.dispatch("The hotel charged me twice.")

    assert (outcome.handled_by, outcome.output) == ("specialist", "dispute handled")


@pytest.mark.parametrize(
    "decision",
    [
        {"category": "other", "confidence": 0.99, "reason": "Not a banking request."},
        {"category": "balance_inquiry", "confidence": 0.69, "reason": "Unclear."},
    ],
)
async def test_other_and_low_confidence_both_go_to_a_person(routed, decision):
    routed(decision)

    outcome = await router.dispatch("Something unusual.")

    assert outcome.handled_by == "human" and len(router.HUMAN_QUEUE) == 1


def test_router_scores_and_the_threshold_trade():
    sample = [
        Scored("dispute", "dispute", 0.95),
        Scored("dispute", "fraud_report", 0.62),
        Scored("fraud_report", "fraud_report", 0.90),
        Scored("fraud_report", "balance_inquiry", 0.81),
        Scored("balance_inquiry", "balance_inquiry", 0.97),
    ]

    assert confusion(sample)[("fraud_report", "balance_inquiry")] == 1
    assert precision_recall(sample, "fraud_report") == (0.5, 0.5)
    low, high = threshold_report(sample, [0.5, 0.85])
    assert (low["to_human"], low["misrouted"]) == (0.0, 0.4)
    assert (high["to_human"], high["misrouted"]) == (0.4, 0.0)


def test_the_canary_split_is_stable_and_close_to_its_share():
    picks = Counter(pick_frontier_model(f"req-{n}") for n in range(20_000))

    assert pick_frontier_model("req-42") == pick_frontier_model("req-42")
    assert 0.04 < picks[MODELS.frontier_canary] / 20_000 < 0.06
    assert pick_frontier_model("req-42", canary_share=0.0) == MODELS.frontier


def step(step_id: str, tool: str, writes: bool = False, what: str = "") -> PlanStep:
    return PlanStep(
        step_id=step_id,
        description=what or step_id,
        tool=tool,
        writes=writes,
        success_check="ok",
    )


TOOLS = {"get_transactions", "screen_counterparty", "place_hold"}


def test_a_plan_is_checked_before_anything_runs():
    plan = Plan(
        goal="g",
        steps=[
            step("s1", "get_transactions"),
            step("s2", "wire_funds", True),
            step("s3", "place_hold", True),
        ],
    )

    problems = validate_plan(plan, TOOLS, max_steps=2)

    assert any("wire_funds" in p for p in problems) and any(
        "budget is 2" in p for p in problems
    )
    assert validate_plan(Plan(goal="g", steps=plan.steps[:1]), TOOLS, max_steps=2) == []


def test_a_revision_cannot_repeat_work_overrun_the_budget_or_replan_forever():
    record = ExecutionRecord(completed={"s1": "42 transactions read"}, replans=0)
    revised = Plan(
        goal="g",
        steps=[step("s1", "get_transactions"), step("s4", "screen_counterparty")],
    )

    assert any(
        "s1 already ran" in p for p in validate_revision(revised, record, TOOLS, 6)
    )
    assert any("budget is 1" in p for p in validate_revision(revised, record, TOOLS, 2))
    exhausted = record.model_copy(update={"replans": 2})
    fresh = Plan(goal="g", steps=[step("s4", "screen_counterparty")])
    assert validate_revision(fresh, exhausted, TOOLS, 6) == [
        "Replan limit reached; send the case to a person."
    ]
    assert validate_revision(fresh, record, TOOLS, 6) == []


def test_a_new_write_in_a_revision_needs_a_fresh_approval():
    approved = Plan(goal="g", steps=[step("s3", "place_hold", True, "Hold account 1")])
    revised = Plan(
        goal="g",
        steps=[
            step("s3", "place_hold", True, "Hold account 1"),
            step("s5", "place_hold", True, "Hold account 2"),
        ],
    )

    assert [s.step_id for s in writes_needing_approval(approved, revised)] == ["s5"]


def view(source: str, risk: str, evidence: list[str]) -> dict:
    return {"source": source, "risk": risk, "evidence": evidence, "summary": "s"}


async def test_specialist_views_are_merged_in_code(monkeypatch):
    replies = [
        view("a", "low", ["txn-1"]),
        view("b", "high", ["txn-2", "txn-1"]),
        view("c", "low", []),
    ]
    agents = [
        scripted(a, says(r)) for a, r in zip(fanout.SPECIALISTS, replies, strict=True)
    ]
    monkeypatch.setattr(fanout, "SPECIALISTS", agents)

    combined = await fanout.gather_specialist_views("case")

    assert combined.risk == "high" and combined.specialists_disagree
    assert combined.evidence == ["txn-1", "txn-2"] and combined.missing == []


async def test_a_missing_specialist_is_reported_and_treated_as_high_risk(monkeypatch):
    agents = [
        scripted(fanout.SPECIALISTS[0], says(view("a", "low", ["txn-1"]))),
        scripted(fanout.SPECIALISTS[1], says("not json")),
        scripted(fanout.SPECIALISTS[2], says(view("c", "low", []))),
    ]
    monkeypatch.setattr(fanout, "SPECIALISTS", agents)

    combined = await fanout.gather_specialist_views("case")

    assert (
        combined.missing == ["transaction_pattern_analyst"] and combined.risk == "high"
    )
