"""Tamper-evident decision records and healthcare audit events."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class DecisionRecord(BaseModel):
    record_id: str
    prev_hash: str
    trace_id: str
    principal: str
    delegation_chain: list[str]
    agent_id: str
    agent_version: str
    model_id: str
    policy_bundle_version: str
    tool_name: str
    args_hash: str
    policy_decision: str
    policy_rule: str
    approver: str | None = None
    outcome: str | None = None
    business_record_ref: str | None = None
    retention_class: str = "audit-7y"
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def content_hash(self) -> str:
        body = self.model_dump(mode="json", exclude={"prev_hash"})
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256((self.prev_hash + payload).encode("utf-8")).hexdigest()


def hash_arguments(arguments: dict[str, Any]) -> str:
    payload = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DecisionChain:
    def __init__(self) -> None:
        self._records: list[DecisionRecord] = []

    @property
    def records(self) -> tuple[DecisionRecord, ...]:
        return tuple(record.model_copy(deep=True) for record in self._records)

    @property
    def head_hash(self) -> str:
        return self._records[-1].content_hash() if self._records else "0" * 64

    def append(self, record: DecisionRecord) -> str:
        if record.prev_hash != self.head_hash:
            raise ValueError("decision record does not extend the current chain")
        self._records.append(record.model_copy(deep=True))
        return record.content_hash()

    def verify(self) -> bool:
        expected = "0" * 64
        for record in self._records:
            if record.prev_hash != expected:
                return False
            expected = record.content_hash()
        return True


def audit_event(
    agent_id: str,
    clinician_ref: str,
    patient_ref: str,
    action: str,
    resource_ref: str,
    outcome: str,
    *,
    recorded_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = recorded_at or datetime.now(timezone.utc)
    return {
        "resourceType": "AuditEvent",
        "type": {
            "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
            "code": "rest",
        },
        "action": action,
        "recorded": timestamp.isoformat(),
        "outcome": outcome,
        "agent": [
            {"who": {"reference": clinician_ref}, "requestor": True},
            {
                "who": {"identifier": {"value": agent_id}},
                "requestor": False,
                "type": {"text": "software agent"},
            },
        ],
        "source": {"observer": {"identifier": {"value": agent_id}}},
        "entity": [
            {"what": {"reference": patient_ref}, "role": {"code": "1"}},
            {"what": {"reference": resource_ref}, "role": {"code": "4"}},
        ],
    }
