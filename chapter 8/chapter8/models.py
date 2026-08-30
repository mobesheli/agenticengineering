"""Typed contracts shared by the Chapter 8 security harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Medication(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    dose: str = Field(min_length=1)
    status: Literal["active", "stopped", "unknown"] = "active"


class PharmacyFill(BaseModel):
    medication_code: str = Field(min_length=1)
    medication_name: str = Field(min_length=1)
    filled_at: datetime
    days_supply: int = Field(gt=0)


class ClinicalNote(BaseModel):
    note_id: str = Field(min_length=1)
    authored_at: datetime
    text: str = Field(min_length=1)
    security_labels: list[str] = Field(default_factory=list)


class PatientFixture(BaseModel):
    patient_id: str = Field(min_length=1)
    patient_name: str = Field(min_length=1)
    date_of_birth: str = Field(min_length=1)
    mrn: str = Field(min_length=1)
    medications: list[Medication]
    recent_fills: list[PharmacyFill]
    allergies: list[str] = Field(default_factory=list)
    notes: list[ClinicalNote] = Field(default_factory=list)


class MedicationChange(BaseModel):
    operation: Literal["add", "review", "stop", "update"]
    medication_code: str = Field(min_length=1)
    medication_name: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class ReconciliationProposal(BaseModel):
    proposal_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    changes: list[MedicationChange]
    source_hashes: dict[str, str] = Field(default_factory=dict)
    detector_flags: list[str] = Field(default_factory=list)
    created_at: datetime

    def write_arguments(self) -> dict[str, Any]:
        reasons = sorted({change.reason_code for change in self.changes})
        return {
            "patient_id": self.patient_id,
            "changes": [change.model_dump(mode="json") for change in self.changes],
            "rationale": ", ".join(reasons) or "no_changes",
        }


@dataclass(frozen=True)
class ApprovalGrant:
    action_hash: str
    approver: str
    approver_role: str
    granted_at: datetime


@dataclass
class SessionContext:
    principal: str
    clinician_ref: str
    patient_id: str
    granted_scopes: frozenset[str]
    expires_at: datetime
    agent_id: str = "medication-reconciliation-agent"
    delegation_chain: tuple[str, ...] = ()
    trace_id: str = ""
    approvals: dict[str, ApprovalGrant] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    allow: bool
    rule: str


@dataclass(frozen=True)
class CatalogDecision:
    allow: bool
    behavior: Literal["allow", "reject", "halt"]
    reason: str
    missing_scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class LintResult:
    present_to_reviewer: bool
    flags: tuple[str, ...] = ()


class SecurityOutcome(BaseModel):
    status: Literal["committed", "denied", "stopped"]
    patient_id: str
    action_hash: str
    policy_rule: str
    business_record_ref: str | None = None
    decision_record_hash: str | None = None
    audit_event: dict[str, Any] | None = None


class DeletionReceipt(BaseModel):
    subject_id: str
    deleted_entries: int = Field(ge=0)
    completed_at: datetime
    receipt_hash: str


class FairnessReport(BaseModel):
    outcome_rates: dict[str, float]
    selection_ratio: float = Field(ge=0)
    threshold: float = Field(gt=0, le=1)
    passes: bool
