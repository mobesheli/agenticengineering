"""Top-level models for the audit-prep agent.

Notice what is not in the request: the identity of the person asking. The
orchestration layer attaches the verified principal and tenant outside the
model-facing schema, in the run context.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class EvidenceRequest(BaseModel):
    control_id: str
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    jurisdiction: Literal["uk", "us", "eu"]


class EvidenceBundleStatus(BaseModel):
    bundle_id: str
    status: Literal["draft", "awaiting_approval",
                    "approved", "published", "failed"]
    artifact_count: int
    awaiting_reviewer_id: Optional[str] = None


class AuditRunContext(BaseModel):
    """What the orchestration layer knows and the model never sees."""

    run_id: str
    principal_id: str
    tenant_id: str
    on_behalf_of: Optional[str] = None
    request: EvidenceRequest
    policy_version: str = "unknown"
