from claims_pipeline.guardrails import is_claim_related, validate_claim_verdict
from claims_pipeline.models import ClaimVerdict


def test_claim_guardrail_accepts_claim_text() -> None:
    text = "Claim CLM-1001 for policy POL-1001 needs review."
    assert is_claim_related(text) is True


def test_claim_guardrail_rejects_unrelated_text() -> None:
    text = "Please summarize this restaurant menu."
    assert is_claim_related(text) is False


def test_verdict_validation_requires_citations() -> None:
    verdict = ClaimVerdict(
        claim_id="CLM-1001",
        decision="approved",
        confidence=0.9,
        cited_sections=[],
        requires_human_review=False,
        explanation="Covered claim.",
    )
    is_valid, message = validate_claim_verdict(verdict)
    assert is_valid is False
    assert "cite" in message.lower()
