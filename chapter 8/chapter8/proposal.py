"""The typed proposal that crosses from the read phase to the write phase."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from chapter8.records import RecordStore
from chapter8.session import Session

Action = Literal["discontinue", "add", "flag_for_review"]
Reason = Literal[
    "duplicate_therapy",
    "filled_not_listed",
    "listed_not_filled",
    "interaction",
    "allergy_conflict",
    "embedded_instruction",
]
TARGET_KIND = {"discontinue": "MedicationRequest/", "add": "MedicationDispense/"}


class Change(BaseModel):
    action: Action
    target: str
    reason: Reason
    evidence: list[str]


class Findings(BaseModel):
    """What the reader returns. It has no field that can carry free text."""

    changes: list[Change]


class Proposal(BaseModel):
    patient_id: str
    record_version: int
    changes: list[Change]


class WriteChange(BaseModel):
    action: Action
    target: str
    reason: Reason


class WriteArguments(BaseModel):
    patient_id: str
    record_version: int
    changes: list[WriteChange]
    note: str


def build_proposal(
    findings: Findings, session: Session, store: RecordStore
) -> Proposal:
    """Patient and record version come from the session and the store, not the model."""
    return Proposal(
        patient_id=session.patient_id,
        record_version=store.version(session.patient_id),
        changes=findings.changes,
    )


def validate_proposal(proposal: Proposal, session: Session) -> list[str]:
    problems = []
    for number, change in enumerate(proposal.changes, start=1):
        cited = [change.target, *change.evidence]
        unread = [record for record in cited if record not in session.seen]
        if unread:
            problems.append(
                f"change {number} cites records this session did not read"
            )
        kind = TARGET_KIND.get(change.action)
        if kind and not change.target.startswith(kind):
            problems.append(f"change {number} targets the wrong kind of record")
        structured = [
            e for e in change.evidence if not e.startswith("DocumentReference/")
        ]
        if change.action != "flag_for_review" and not structured:
            problems.append(f"change {number} rests on a note alone")
    targets = [(change.action, change.target) for change in proposal.changes]
    if len(targets) != len(set(targets)):
        problems.append("the same change appears twice")
    return problems


def same_changes(proposal: Proposal, arguments: WriteArguments) -> bool:
    """True when the write asks for exactly what the validated proposal contains."""
    proposed = {(c.action, c.target, c.reason) for c in proposal.changes}
    asked = {(c.action, c.target, c.reason) for c in arguments.changes}
    return (
        proposed == asked
        and arguments.patient_id == proposal.patient_id
        and arguments.record_version == proposal.record_version
    )
