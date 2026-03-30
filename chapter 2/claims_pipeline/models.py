from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PolicyRecord(BaseModel):
    policy_number: str
    policyholder_id: str
    covered_incidents: dict[str, str]
    sections: dict[str, str]
    deductible: float
    coverage_limit: float


class ClaimRecord(BaseModel):
    claim_id: str
    policy_number: str
    policyholder_id: str
    incident_type: str
    amount: float
    date_of_loss: str
    submitted_documents: list[str]
    summary: str


class TopicCheck(BaseModel):
    is_relevant: bool


class IntakeResult(BaseModel):
    claim_id: str
    is_complete: bool
    missing_documents: list[str]
    next_step: Literal["review", "request_documents"]


class ClaimVerdict(BaseModel):
    claim_id: str
    decision: Literal["approved", "denied", "needs_human_review"]
    confidence: float = Field(ge=0.0, le=1.0)
    cited_sections: list[str]
    requires_human_review: bool
    explanation: str


class EscalationReport(BaseModel):
    claim_id: str
    reason: str
    recommended_action: str


class PipelineResult(BaseModel):
    claim_id: str
    stage: Literal["request_documents", "review_complete", "escalated"]
    intake: IntakeResult
    verdict: ClaimVerdict | None = None
    escalation: EscalationReport | None = None
