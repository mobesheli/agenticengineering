from claims_pipeline.data import get_claim
from claims_pipeline.models import ClaimVerdict
from claims_pipeline.pipeline import _enforce_manual_review_rules, run_offline_pipeline


def test_offline_pipeline_approves_complete_claim() -> None:
    result = run_offline_pipeline("CLM-1001")
    assert result.stage == "review_complete"
    assert result.intake.is_complete is True
    assert result.verdict is not None
    assert result.verdict.decision == "approved"


def test_offline_pipeline_requests_missing_documents() -> None:
    result = run_offline_pipeline("CLM-1002")
    assert result.stage == "request_documents"
    assert result.intake.is_complete is False
    assert result.intake.missing_documents == ["police_report"]
    assert result.verdict is None


def test_offline_pipeline_escalates_high_risk_claim() -> None:
    result = run_offline_pipeline("CLM-1003")
    assert result.stage == "escalated"
    assert result.verdict is not None
    assert result.verdict.requires_human_review is True
    assert result.escalation is not None


def test_manual_review_rules_override_an_optimistic_model_verdict() -> None:
    claim = get_claim("CLM-1003")
    verdict = ClaimVerdict(
        claim_id="CLM-1003",
        decision="approved",
        confidence=0.95,
        cited_sections=["SECTION_A_WATER"],
        requires_human_review=False,
        explanation="Model approved the claim.",
    )
    adjusted = _enforce_manual_review_rules(claim, verdict)
    assert adjusted.decision == "needs_human_review"
    assert adjusted.requires_human_review is True
    assert "SECTION_C_ESCALATION" in adjusted.cited_sections
