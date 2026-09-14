from __future__ import annotations

import pytest

from chapter9.budget import BudgetExhausted, LoopDetected, RunBudget
from chapter9.pricing import load_price_card


def budget(**changes) -> RunBudget:
    values = {
        "price_card": load_price_card(),
        "limit_usd": 1.0,
        "max_calls": 5,
        "max_steps": 5,
        "max_seconds": 30,
    }
    values.update(changes)
    return RunBudget(**values)


def test_reservation_happens_before_call_and_settlement_replaces_estimate() -> None:
    run = budget()
    reservation = run.reserve("model:maintenance-mid", 0.20)
    assert run.remaining_usd == pytest.approx(0.80)
    run.settle(reservation, 0.12)
    assert run.spent_usd == pytest.approx(0.12)
    assert run.remaining_usd == pytest.approx(0.88)


def test_exact_tool_loop_is_refused_without_spending_or_incrementing_calls() -> None:
    run = budget()
    args = {"asset_id": "A-1", "fault": "bearing"}
    first = run.reserve_tool("check_parts_catalog", args)
    run.settle(first, 0.02)
    calls = run.calls
    with pytest.raises(LoopDetected, match="already ran"):
        run.reserve_tool("check_parts_catalog", args)
    assert run.calls == calls
    assert run.spent_usd == pytest.approx(0.02)


def test_unknown_tool_is_not_treated_as_free() -> None:
    run = budget()
    with pytest.raises(KeyError, match="unknown tools fail closed"):
        run.reserve_tool("new_unpriced_tool", {})


def test_budget_refuses_call_that_would_cross_cost_limit() -> None:
    run = budget(limit_usd=0.01)
    with pytest.raises(BudgetExhausted, match="cost_budget_exhausted"):
        run.reserve("tool:expensive", 0.02)
    assert run.stop_reason == "cost_budget_exhausted"


def test_child_cannot_mint_more_than_parent_remainder() -> None:
    run = budget(limit_usd=0.25)
    reservation = run.reserve("model", 0.10)
    with pytest.raises(BudgetExhausted, match="cannot mint"):
        run.child(limit_usd=0.20, max_calls=1, max_steps=1)
    run.cancel(reservation)
    run = budget(limit_usd=0.25)
    child = run.child(limit_usd=0.20, max_calls=1, max_steps=1)
    assert child.limit_usd == 0.20
    assert run.remaining_usd == pytest.approx(0.05)
    child_call = child.reserve_tool("check_parts_catalog", {"asset_id": "A-2"})
    child.settle(child_call, 0.02)
    run.absorb_child(child)
    assert run.spent_usd == pytest.approx(0.02)
    assert run.remaining_usd == pytest.approx(0.23)
