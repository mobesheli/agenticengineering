"""The decision record, the hash chain, the signed checkpoint, and FHIR audit events."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from chapter8.session import Session

GENESIS = "0" * 64
AUDIT_TYPES = "http://terminology.hl7.org/CodeSystem/audit-event-type"
OBJECT_ROLES = "http://terminology.hl7.org/CodeSystem/object-role"


class DecisionRecord(BaseModel):
    decision_id: str
    kind: Literal["authorized", "denied", "executed", "failed"]
    trace_id: str
    principal: str
    delegation: list[str]
    agent_id: str
    agent_version: str
    model_id: str
    policy_version: str
    tool: str
    arguments_sha256: str
    rule: str
    approver: str | None = None
    business_ref: str | None = None
    retention: str = "audit"
    recorded_at: datetime
    prev_hash: str = GENESIS

    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


@dataclass(frozen=True)
class Checkpoint:
    count: int
    head: str
    signature: str


class DecisionLog:
    """Append-only at the interface. The agent holds no credential for it."""

    def __init__(self) -> None:
        self._records: list[DecisionRecord] = []

    def append(self, record: DecisionRecord) -> DecisionRecord:
        chained = record.model_copy(update={"prev_hash": self.head()})
        self._records.append(chained)
        return chained

    def head(self) -> str:
        return self._records[-1].digest() if self._records else GENESIS

    def records(self) -> list[DecisionRecord]:
        return list(self._records)


class Notary:
    """Signs the head of the chain. It runs apart from the log, with its own key."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    def _sign(self, count: int, head: str) -> str:
        message = f"{count}:{head}".encode()
        return hmac.new(self._key, message, hashlib.sha256).hexdigest()

    def checkpoint(self, log: DecisionLog) -> Checkpoint:
        count, head = len(log.records()), log.head()
        return Checkpoint(count, head, self._sign(count, head))

    def verify(self, records: list[DecisionRecord], mark: Checkpoint) -> str:
        if not hmac.compare_digest(
            mark.signature, self._sign(mark.count, mark.head)
        ):
            return "checkpoint signature is not valid"
        if len(records) < mark.count:
            missing = mark.count - len(records)
            return f"records missing since the checkpoint: {missing}"
        previous = GENESIS
        for number, record in enumerate(records[: mark.count], start=1):
            if record.prev_hash != previous:
                return f"chain breaks at record {number}"
            previous = record.digest()
        if previous != mark.head:
            return f"record {mark.count} does not match the checkpoint"
        return "intact"


def audit_event(
    session: Session, action: str, what: str, outcome: str, at: datetime
) -> dict[str, Any]:
    """A FHIR R4 AuditEvent. The record server writes it, not the agent."""
    return {
        "resourceType": "AuditEvent",
        "type": {"system": AUDIT_TYPES, "code": "rest"},
        "action": action,
        "recorded": at.isoformat(),
        "outcome": outcome,
        "agent": [
            {"who": {"reference": session.clinician}, "requestor": True},
            {
                "who": {"identifier": {"value": session.agent_id}},
                "requestor": False,
                "type": {"text": "software agent"},
            },
        ],
        "source": {"observer": {"display": "ehr-records"}},
        "entity": [
            {
                "what": {"reference": f"Patient/{session.patient_id}"},
                "role": {"system": OBJECT_ROLES, "code": "1"},
            },
            {
                "what": {"reference": what},
                "role": {"system": OBJECT_ROLES, "code": "4"},
            },
        ],
    }
