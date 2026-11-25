"""The price card, the meter, and the run budget."""

import pytest

from chapter9.budget import BudgetExceeded, RunBudget
from chapter9.meter import price_usage, usage_of
from chapter9.pricecard import UnknownPrice, load_price_card
from chapter9.turn import Turn, variants

CARD = load_price_card()
SOL = CARD.rates("gpt-6.2-sol")


def test_usage_is_split_into_five_lines_that_add_up():
    cost = price_usage(usage_of(10_000, 2_000, 6_000, 1_000, 1_200), SOL)
    assert cost.uncached_input == pytest.approx(3_000 * 2.00 / 1e6)
    assert cost.cached_input == pytest.approx(6_000 * 0.10 / 1e6)
    assert cost.cache_write == pytest.approx(1_000 * 2.50 / 1e6)
    assert cost.reasoning == pytest.approx(1_200 * 10.00 / 1e6)
    assert cost.visible_output == pytest.approx(800 * 10.00 / 1e6)
    assert cost.total == pytest.approx(0.0291)


def test_reasoning_is_part_of_output_and_is_not_charged_twice():
    with_reasoning = price_usage(usage_of(0, 2_000, reasoning=1_500), SOL)
    without = price_usage(usage_of(0, 2_000), SOL)
    assert with_reasoning.total == pytest.approx(without.total)


def test_a_model_that_is_not_on_the_card_is_an_error():
    with pytest.raises(UnknownPrice):
        CARD.rates("gpt-7-preview")
    with pytest.raises(UnknownPrice):
        CARD.tool_fee("send_email")


def test_a_rewritten_cache_costs_more_than_no_cache():
    costs = variants(Turn(), CARD.rates("gpt-6.1-terra"))
    plain = costs["nothing cached"].total
    assert costs["prefix cached"].total < plain / 2
    assert costs["prefix changed, cache rewritten"].total > plain


def test_budget_reserves_then_settles_to_the_real_cost():
    budget = RunBudget(1.00)
    budget.reserve(0.10, "model")
    assert budget.remaining_usd == pytest.approx(0.90)
    budget.settle(0.10, 0.04)
    assert budget.spent_usd == pytest.approx(0.04)
    assert budget.remaining_usd == pytest.approx(0.96)
    assert budget.estimate() == pytest.approx(0.04)


def test_budget_stops_before_the_action_that_would_exceed_it():
    budget = RunBudget(0.05)
    budget.reserve(0.04, "model")
    budget.settle(0.04, 0.04)
    with pytest.raises(BudgetExceeded) as stop:
        budget.reserve(0.04, "model")
    assert stop.value.spent == pytest.approx(0.04)
    assert budget.spent_usd == pytest.approx(0.04)
    assert budget.stops == ["run budget exhausted"]


def test_budget_counts_calls_as_well_as_dollars():
    budget = RunBudget(1.00, model_calls=1)
    budget.reserve(0.01, "model")
    with pytest.raises(BudgetExceeded, match="no model calls left"):
        budget.reserve(0.01, "model")


def test_a_child_draws_on_its_parent_and_cannot_add_to_it():
    parent = RunBudget(0.10)
    child = parent.child(0.50)
    assert child.limit_usd == pytest.approx(0.10)
    child.reserve(0.06, "model")
    child.settle(0.06, 0.06)
    assert parent.spent_usd == pytest.approx(0.06)
    second = parent.child(0.50)
    with pytest.raises(BudgetExceeded):
        second.reserve(0.05, "model")


def test_an_exact_repeat_is_noticed_once_it_has_been_seen():
    budget = RunBudget(1.00)
    assert not budget.repeated("check_parts", '{"part_number":"A"}')
    assert budget.repeated("check_parts", '{"part_number":"A"}')
    assert not budget.repeated("check_parts", '{"part_number":"B"}')
