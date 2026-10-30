from copy import deepcopy

import pytest
from pydantic import ValidationError

from chapter11.artifacts import load_json
from chapter11.autonomy import (
    action_route,
    load_rules,
    pass_hat_k,
    promote,
    promotion_digest,
    promotion_gaps,
    should_drop,
)
from chapter11.board import replay
from chapter11.drift import Decision, configuration_changes, decide, fallback_drill
from chapter11.models import (
    AgentEntry,
    Approval,
    PromotionEvidence,
    Reading,
    RunConfiguration,
)


def readings(**changes):
    return [
        Reading.model_validate({**r, "value": changes.get(r["signal"], r["value"])})
        for r in load_json("readings.json")
    ]


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({}, Decision.OK),
        ({"outcome": 0.92}, Decision.PROPOSE),
        ({"outcome": 0.6}, Decision.RERUN),
        ({"input": 1.5}, Decision.RERUN),
        ({"outcome": 0.92, "cost_speed": 1.3}, Decision.BUDGET),
    ],
)
def test_drift_priority(changes, expected):
    assert decide(readings(**changes), True) == expected
    assert decide(readings(**changes), False) == Decision.HOLD


def test_missing_and_duplicate_signals_hold():
    assert decide(readings()[:-1], True) == Decision.HOLD
    assert decide([readings()[0]] * 5, True) == Decision.HOLD


def test_zero_baseline_and_exact_boundary():
    assert not Reading(signal="knowledge", baseline=0, value=0, band=0.1).moved
    assert Reading(signal="knowledge", baseline=0, value=0.1, band=0.1).moved
    assert not Reading(signal="cost_speed", baseline=10, value=11, band=0.1).moved
    with pytest.raises(ValidationError):
        Reading(signal="input", baseline=1, value=float("nan"), band=0.1)


def test_configuration_checks_settings_not_only_model_name():
    pinned = RunConfiguration.model_validate(load_json("configuration.json"))
    effective = pinned.model_copy(update={"reasoning_effort": "high"})
    assert configuration_changes(pinned, effective) == ["reasoning_effort"]


def test_uncertified_fallback_pauses():
    secondary = load_json("fallback.json")
    assert (
        fallback_drill("frontier-v2", secondary, secondary["suite"])["status"]
        == "degraded"
    )
    secondary["cached"] = True
    assert fallback_drill("frontier-v2", secondary, secondary["suite"])["route"] is None


def case():
    entry = AgentEntry.model_validate(replay(130)["entry"])
    evidence = PromotionEvidence.model_validate(load_json("promotion-evidence.json"))
    return entry, evidence, load_rules()[2]


def approvals(entry, evidence, rule):
    subject = promotion_digest(entry, evidence, rule.target)
    return [
        Approval(role="sponsor", name=entry.sponsor, subject_digest=subject),
        Approval(role="security", name="Jordan Lee", subject_digest=subject),
    ]


def test_ceiling_is_checked_before_other_evidence():
    entry, evidence, rule = case()
    entry.ceiling = 1
    assert promotion_gaps(entry, evidence, rule, 2, day=130) == [
        "above this agent's ceiling; only the risk owners can move it"
    ]


def test_pass_k_means_every_trial_and_enforces_k():
    assert pass_hat_k([[True] * 8, [True] * 7 + [False]], 8) == 0.5
    for trials in ([], [[True] * 7], [[1] * 8]):
        with pytest.raises(ValueError):
            pass_hat_k(trials, 8)


@pytest.mark.parametrize(
    "change,fragment",
    [
        ({"planted_caught": 1}, "reviewers missed"),
        ({"observed_days": 3}, "observation window"),
        ({"days_since_incident": 3}, "incident-free"),
        ({"cost_in_band": False}, "cost per"),
        ({"bundle": "other@1"}, "different release"),
        ({"trials": [[True] * 7]}, "exactly 8"),
        ({"reviewer_miss_rate": None}, "miss rate"),
        ({"exception_rate_stable": False}, "exception rate"),
    ],
)
def test_promotion_names_evidence_gaps(change, fragment):
    entry, evidence, rule = case()
    evidence = PromotionEvidence.model_validate({**evidence.model_dump(), **change})
    assert any(
        fragment in gap for gap in promotion_gaps(entry, evidence, rule, 2, day=130)
    )


def test_bound_approvals_and_expired_sponsor():
    entry, evidence, rule = case()
    signed = approvals(entry, evidence, rule)
    assert promote(entry, evidence, rule, signed, day=130).rung == 2
    with pytest.raises(ValueError, match="approval"):
        promote(entry, evidence, rule, [], day=130)
    changed = deepcopy(evidence)
    changed.planted_caught = 20
    with pytest.raises(ValueError, match="approval"):
        promote(entry, changed, rule, signed, day=130)
    with pytest.raises(ValueError, match="attestation"):
        promote(entry, evidence, rule, signed, day=180)


def test_drop_boundary_and_safety_actions():
    entry, _, rule = case()
    assert should_drop(
        {"consecutive_denials": 3, "denials": 3, "drift_hold_active": False}, rule
    )
    assert not should_drop(
        {"consecutive_denials": 2, "denials": 19, "drift_hold_active": False}, rule
    )
    entry.rung = 3
    assert action_route(entry, "routine_work_order") == "automatic"
    for action in ("lockout", "safety_critical", "unknown"):
        assert action_route(entry, action) == "approval"
    assert action_route(entry, "routine_work_order", irreversible=True) == "approval"
    entry.rung = 0
    assert action_route(entry, "routine_work_order") == "draft_only"


def test_audited_autonomy_requires_review_and_recent_drill():
    entry = AgentEntry.model_validate(replay(200)["entry"])
    evidence = PromotionEvidence.model_validate(load_json("promotion-evidence.json"))
    evidence.drill_age_days = 91
    evidence.unreviewed_irreversible_actions = 1
    gaps = promotion_gaps(entry, evidence, load_rules()[3], 3, day=200)
    assert any("kill-switch" in g for g in gaps)
    assert any("irreversible" in g for g in gaps)


def test_configuration_hold_blocks_actions_and_promotion():
    entry, evidence, rule = case()
    entry.drift_hold_active = True
    assert action_route(entry, "routine_work_order") == "refused"
    assert "an active drift hold blocks promotion" in promotion_gaps(
        entry, evidence, rule, 2, day=130
    )
