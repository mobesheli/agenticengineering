"""Short-lived, patient-scoped identity contexts for the healthcare pattern."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import SessionContext


@dataclass(frozen=True)
class PhaseScopes:
    read_phase: frozenset[str]
    write_phase: frozenset[str]


RECONCILIATION = PhaseScopes(
    read_phase=frozenset(
        {
            "patient/MedicationRequest.rs",
            "patient/MedicationStatement.rs",
            "patient/MedicationDispense.rs",
            "patient/AllergyIntolerance.rs",
            "patient/Observation.rs?category=laboratory",
            "patient/Condition.rs?category=problem-list-item",
        }
    ),
    write_phase=frozenset(),
)

CLINICIAN_WRITE_SCOPE = "patient/MedicationRequest.c"


def scopes_for(phase: str) -> frozenset[str]:
    if phase == "read":
        return RECONCILIATION.read_phase
    if phase == "write":
        return RECONCILIATION.write_phase
    raise ValueError(f"unknown phase: {phase}")


def clinician_read_session(
    *,
    clinician_ref: str,
    patient_id: str,
    now: datetime | None = None,
    ttl: timedelta = timedelta(minutes=5),
    trace_id: str = "",
) -> SessionContext:
    issued_at = now or datetime.now(timezone.utc)
    return SessionContext(
        principal=clinician_ref,
        clinician_ref=clinician_ref,
        patient_id=patient_id,
        granted_scopes=scopes_for("read"),
        expires_at=issued_at + ttl,
        delegation_chain=(clinician_ref, "medication-reconciliation-agent"),
        trace_id=trace_id,
    )


def clinician_write_session(
    *,
    clinician_ref: str,
    patient_id: str,
    now: datetime | None = None,
    ttl: timedelta = timedelta(minutes=5),
    trace_id: str = "",
) -> SessionContext:
    issued_at = now or datetime.now(timezone.utc)
    return SessionContext(
        principal=clinician_ref,
        clinician_ref=clinician_ref,
        patient_id=patient_id,
        granted_scopes=frozenset({CLINICIAN_WRITE_SCOPE}),
        expires_at=issued_at + ttl,
        delegation_chain=(clinician_ref, "clinical-approval-service"),
        trace_id=trace_id,
    )


def require_active_session(session: SessionContext, now: datetime) -> None:
    if session.expires_at <= now:
        raise PermissionError("session credential has expired")
