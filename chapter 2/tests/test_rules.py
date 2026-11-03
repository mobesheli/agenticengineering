from claims_pipeline.models import ClaimVerdict
from claims_pipeline.rules import escalation_reasons, needs_escalation


def verdict(**overrides) -> ClaimVerdict:
    base = dict(
        decision="approve",
        confidence=0.97,
        cited_sections=["Perils Insured Against"],
        requires_human_review=False,
        explanation="Sudden pipe burst is a covered peril.",
    )
    base.update(overrides)
    return ClaimVerdict(**base)


def test_confident_small_claim_is_not_escalated():
    assert needs_escalation(verdict(), amount_usd=23_500.0) is False


def test_amount_over_limit_escalates_even_when_model_is_confident():
    assert needs_escalation(verdict(), amount_usd=86_000.0) is True


def test_low_confidence_escalates():
    assert needs_escalation(verdict(confidence=0.72), amount_usd=5_000.0) is True


def test_model_flag_is_respected_but_not_required():
    assert needs_escalation(verdict(requires_human_review=True), amount_usd=5_000.0) is True


def test_reasons_name_every_tripped_rule():
    reasons = escalation_reasons(verdict(confidence=0.5), amount_usd=90_000.0)
    assert len(reasons) == 2
    assert any("Confidence" in reason for reason in reasons)
    assert any("exceeds" in reason for reason in reasons)


def test_verdict_schema_rejects_out_of_range_confidence():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        verdict(confidence=1.4)
    with pytest.raises(ValidationError):
        verdict(decision="maybe")
