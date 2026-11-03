"""Pydantic models that define the data flowing through the pipeline."""

from typing import Literal

from pydantic import BaseModel, Field

ClaimCategory = Literal["property", "auto", "liability", "workers_comp"]


class TopicCheck(BaseModel):
    is_relevant: bool
    reason: str


class IntakeResult(BaseModel):
    is_complete: bool
    missing_documents: list[str]
    claim_category: ClaimCategory
    priority: Literal["standard", "urgent"]


class ClaimVerdict(BaseModel):
    decision: Literal["approve", "deny", "investigate"]
    confidence: float = Field(ge=0.0, le=1.0)
    cited_sections: list[str]
    requires_human_review: bool
    explanation: str


class EscalationReport(BaseModel):
    summary: str
    reasons: list[str]
    recommended_action: str


class Claim(BaseModel):
    claim_id: str
    policy_number: str
    policyholder_id: str
    claim_type: ClaimCategory
    amount_usd: float = Field(gt=0)
    date_of_loss: str
    submitted_documents: list[str]
    description: str
    raw_submission: str | None = None

    def as_text(self) -> str:
        if self.raw_submission:
            return self.raw_submission
        documents = ", ".join(self.submitted_documents)
        return (
            f"Claim {self.claim_id}: {self.description} "
            f"Policy: {self.policy_number}. Policyholder: {self.policyholder_id}. "
            f"Claim type: {self.claim_type}. Date of loss: {self.date_of_loss}. "
            f"Submitted documents: {documents}. "
            f"Estimated damage: ${self.amount_usd:,.2f}."
        )


class PipelineOutcome(BaseModel):
    status: Literal["rejected", "incomplete", "processed", "escalated"]
    claim_id: str
    trace_id: str
    reason: str | None = None
    missing_documents: list[str] = []
    verdict: ClaimVerdict | None = None
    report: EscalationReport | None = None
