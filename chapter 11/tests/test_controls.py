"""Drift, the effective configuration, the ladder, and the mandate."""

from agents.tracing import response_span, set_trace_processors, trace
from openai.types.responses import Response, ResponseTextConfig
from openai.types.shared import Reasoning

from chapter11.autonomy import promotion_gaps, should_drop
from chapter11.drift import Decision, Reading, decide
from chapter11.effective import ConfigWatch, differences, effective_configuration
from chapter11.mandate import Mandate, authorize, revoke
from chapter11.settings import load


def readings(**values):
    bands = load("readings")["bands"]
    return [
        Reading(
            name,
            values.get(name.split()[0], band["baseline"]),
            band["baseline"],
            band["band"],
        )
        for name, band in bands.items()
    ]


def response(
    model="gpt-6.1-terra", effort="low", verbosity="medium", top_p=0.98
):
    return Response.model_construct(
        id="resp_1",
        model=model,
        reasoning=Reasoning(effort=effort),
        text=ResponseTextConfig(verbosity=verbosity),
        service_tier="default",
        truncation="disabled",
        temperature=1.0,
        top_p=top_p,
        parallel_tool_calls=True,
        max_output_tokens=None,
    )


def test_the_effective_configuration_is_read_from_the_response():
    approved = load("bundle")["observed_at_approval"]
    assert differences(approved, effective_configuration(response())) == {}
    moved = effective_configuration(response(verbosity="high"))
    assert differences(approved, moved) == {"text.verbosity": ("medium", "high")}


def test_a_setting_that_moved_is_named_with_both_values():
    approved = load("bundle")["observed_at_approval"]
    changed = differences(
        approved, effective_configuration(response(effort="high"))
    )
    assert changed == {"reasoning.effort": ("low", "high")}


def test_the_watch_collects_the_configuration_from_a_response_span():
    watch = ConfigWatch()
    set_trace_processors([watch])
    with (
        trace("maintenance work order") as run,
        response_span(response=response()),
    ):
        pass
    assert watch.seen[run.trace_id]["text.verbosity"] == "medium"
    set_trace_processors([])


def test_a_configuration_that_is_not_the_bundle_holds_and_opens_a_candidate():
    verdict = decide(readings(outcome=0.86), {"model": ("a", "b")})
    assert verdict.decision is Decision.HOLD and verdict.candidate


def test_nothing_moved_is_ok():
    assert decide(readings(), {}).decision is Decision.OK


def test_cost_outside_its_band_is_a_budget_review_even_when_outcome_improved():
    verdict = decide(readings(cost=3.40, outcome=0.90), {})
    assert verdict.decision is Decision.BUDGET


def test_better_outcome_alone_is_a_proposal_and_worse_is_a_rerun():
    assert decide(readings(outcome=0.86), {}).decision is Decision.PROPOSE
    assert decide(readings(outcome=0.79), {}).decision is Decision.RERUN
    assert decide(readings(knowledge=0.09), {}).decision is Decision.RERUN


def test_a_zero_baseline_is_an_ordinary_reading():
    quiet = Reading("refusals", 0.0, 0.0, 0.01)
    loud = Reading("refusals", 0.04, 0.0, 0.01)
    assert not quiet.moved and loud.moved
    assert decide([loud], {}).decision is Decision.RERUN


def test_the_ceiling_is_checked_first_and_answers_alone():
    rule = load("ladder")["rung_1_to_2"]
    gaps = promotion_gaps({}, rule, target=2, ceiling=1)
    assert gaps == ["rung 2 is above this agent's ceiling of 1"]


def test_missing_evidence_is_a_gap_and_never_an_error():
    rule = load("ladder")["rung_1_to_2"]
    gaps = promotion_gaps({"incident_free_days": 10}, rule, 2, 3)
    assert len(gaps) == 4
    assert "pass_hat_k_must_always_work: no evidence on record" in gaps
    assert "incident_free_days: 10 is below the required 60" in gaps


def test_every_key_the_rules_require_is_in_the_evidence_on_file():
    ladder, data = load("ladder"), load("evidence")
    assert set(ladder["rung_1_to_2"]["require"]) == set(
        data["day_175"]["evidence"]
    )
    assert (
        promotion_gaps(data["day_175"]["evidence"], ladder["rung_1_to_2"], 2, 3)
        == []
    )


def test_a_high_approval_rate_is_not_in_the_rule():
    rule = load("ladder")["rung_1_to_2"]
    assert not any("approval" in name for name in rule["require"])


def test_the_drop_rule_fires_on_denials_and_on_a_drift_hold():
    rule = load("ladder")["rung_1_to_2"]
    assert should_drop({"consecutive_denials": 3}, rule)
    assert should_drop({"drift_hold": True}, rule) == ["drift_hold"]
    assert (
        should_drop({"consecutive_denials": 2, "shift_denials": 5}, rule) == []
    )


def mandate():
    terms = load("mandate")["mandate"]
    return Mandate(**{**terms, "suppliers": tuple(terms["suppliers"])})


def test_the_mandate_refuses_what_it_does_not_cover():
    m = mandate()
    order = {"id": "x", "day": 201, "supplier": "NordBolt", "usd": 180}
    assert authorize(order, m) is None
    assert "order cap" in authorize({**order, "usd": 401}, m)
    assert "not on the mandate" in authorize({**order, "supplier": "Other"}, m)
    assert authorize({**order, "day": 271}, m) == "mandate expired"


def test_the_daily_cap_counts_what_is_already_placed():
    m = mandate()
    for _ in range(2):
        assert (
            authorize(
                {"id": "x", "day": 5, "supplier": "NordBolt", "usd": 400}, m
            )
            is None
        )
    assert "day's cap" in authorize(
        {"id": "y", "day": 5, "supplier": "NordBolt", "usd": 300}, m
    )
    assert (
        authorize({"id": "z", "day": 6, "supplier": "NordBolt", "usd": 300}, m)
        is None
    )


def test_revoking_stops_the_next_order_and_returns_the_ones_already_placed():
    m = mandate()
    authorize({"id": "a", "day": 5, "supplier": "NordBolt", "usd": 100}, m)
    open_orders = revoke(m)
    assert [o["id"] for o in open_orders] == ["a"]
    assert (
        authorize({"id": "b", "day": 5, "supplier": "NordBolt", "usd": 1}, m)
        == "mandate revoked"
    )
