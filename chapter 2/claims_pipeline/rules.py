"""Business rules that are enforced in code, not delegated to the model."""

from .models import ClaimVerdict
from .settings import ESCALATION_AMOUNT_USD, ESCALATION_CONFIDENCE


def needs_escalation(verdict: ClaimVerdict, amount_usd: float) -> bool:
    return (
        verdict.requires_human_review
        or verdict.confidence < ESCALATION_CONFIDENCE
        or amount_usd > ESCALATION_AMOUNT_USD
    )


def escalation_reasons(verdict: ClaimVerdict, amount_usd: float) -> list[str]:
    reasons: list[str] = []
    if verdict.requires_human_review:
        reasons.append("The reviewer flagged the claim for human review.")
    if verdict.confidence < ESCALATION_CONFIDENCE:
        reasons.append(
            f"Confidence {verdict.confidence:.2f} is below the "
            f"{ESCALATION_CONFIDENCE:.2f} threshold."
        )
    if amount_usd > ESCALATION_AMOUNT_USD:
        reasons.append(
            f"Claim amount ${amount_usd:,.2f} exceeds the "
            f"${ESCALATION_AMOUNT_USD:,.0f} autonomous approval limit."
        )
    return reasons
