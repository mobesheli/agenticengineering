"""The reports, on the synthetic months."""

import math
from dataclasses import replace

import pytest
import yaml

from chapter9.ledger import SUCCESS
from chapter9.month import load_month
from chapter9.pricecard import load_price_card
from chapter9.report import (
    bill_change,
    cost_per_outcome,
    metrics,
    reconcile,
    token_share_by_step,
    unit_cost,
    verdict,
    wilson,
)
from chapter9.settings import DATA
from examples.common import baseline

CARD = load_price_card()
BEFORE = load_month("before", CARD)[1]
AFTER = load_month("after", CARD)[1]


def test_the_month_expands_to_one_record_for_each_run():
    assert len(BEFORE) == 6_000
    assert sum(run.outcome == SUCCESS for run in BEFORE) == 4_260
    assert len({run.trace_id for run in BEFORE}) == 6_000


def test_unit_cost_is_the_table_in_the_chapter():
    cost = unit_cost(BEFORE, CARD)
    assert round(cost["lines"]["model tokens"], 2) == 0.34
    assert round(cost["lines"]["human review"], 2) == 2.94
    assert round(cost["per_attempt"], 2) == 3.40
    assert round(cost["per_approved"], 2) == 4.79


def test_a_cheaper_attempt_can_make_a_dearer_order():
    candidate = unit_cost(load_month("candidate", CARD)[1], CARD)
    current = unit_cost(BEFORE, CARD)
    assert candidate["per_attempt"] < current["per_attempt"]
    assert candidate["per_approved"] > current["per_approved"]


def test_the_interval_behaves_at_the_edges():
    assert wilson(0, 0) == (0.0, 1.0)
    low, high = wilson(0, 20)
    assert low == 0.0 and 0.0 < high < 0.2
    low, high = wilson(20, 20)
    assert 0.8 < low < 1.0 and high == 1.0
    low, high = wilson(360, 400)
    assert high - low == pytest.approx(0.06, abs=0.005)


def test_the_verdict_uses_both_ends_of_the_interval():
    assert verdict(100.0, 100, 0.50, 0.60, 3.00) == "below baseline"
    assert verdict(100.0, 100, 0.50, 0.60, 1.50) == "above baseline"
    assert verdict(100.0, 100, 0.50, 0.60, 1.80) == "at baseline"
    assert verdict(100.0, 100, 0.0, 0.10, 1.80) == "no reliable rate"
    assert verdict(100.0, 100, 0.50, 0.60, math.nan) == "no baseline"


def test_plants_differ_until_the_work_is_compared_like_for_like():
    human = baseline()
    by_plant = {
        r["plant"]: r
        for r in cost_per_outcome(BEFORE, CARD, human, by=("plant",))
    }
    assert (
        by_plant["plant-1"]["usd_per_approved"]
        > 1.4 * by_plant["plant-2"]["usd_per_approved"]
    )
    routine = [
        r
        for r in cost_per_outcome(BEFORE, CARD, human)
        if r["severity"] == "routine"
    ]
    spread = [r["usd_per_approved"] for r in routine]
    assert max(spread) / min(spread) < 1.05


def test_a_group_with_no_approvals_or_no_baseline_has_no_number_to_misread():
    some = [run for run in BEFORE if run.identity["plant"] == "plant-4"][:5]
    copies = [replace(run, outcome="rejected") for run in some]
    row = cost_per_outcome(copies, CARD, {})[0]
    assert row["usd_per_approved"] is None and row["baseline_usd"] is None
    assert row["verdict"] == "no baseline"


def test_token_share_adds_up_and_ranks_by_spend():
    rows = token_share_by_step(BEFORE)
    assert sum(row["share"] for row in rows) == pytest.approx(1.0)
    assert rows[0]["step"] == "read" and rows[0]["share"] > 0.7


def test_the_bill_tripled_while_the_price_halved():
    earlier = yaml.safe_load((DATA / "earlier.yaml").read_text())
    change = bill_change(earlier, BEFORE)
    assert change["usd_per_million_tokens_x"] == pytest.approx(0.5, abs=0.001)
    assert change["bill_x"] == pytest.approx(3.0, abs=0.001)


def test_the_ledger_reconciles_with_the_invoice():
    check = reconcile(BEFORE, 2071.30, 0.03)
    assert check["within_tolerance"] and check["gap"] == pytest.approx(
        0.0151, abs=0.0001
    )
    assert not reconcile(BEFORE, 3400.00, 0.03)["within_tolerance"]


def test_the_metrics_move_the_way_the_changes_intended():
    then, now = metrics(BEFORE), metrics(AFTER)
    assert then["loop_rate"] > 0.09 and now["loop_rate"] == 0.0
    assert then["cache_hit_rate"] == 0.0 and now["cache_hit_rate"] > 0.8
    assert now["turns_p95"] < then["turns_p95"]
