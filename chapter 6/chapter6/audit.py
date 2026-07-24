"""Boundary audit records: the local trace ends where the wire begins."""

from __future__ import annotations

import hashlib

from .contracts import AuditEvent, TaskOutcome
from .registry import CounterpartyEntry


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class BoundaryAuditLog:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def record_exchange(
        self,
        *,
        event_type: str,
        entry: CounterpartyEntry,
        request_payload: str,
        outcome: TaskOutcome,
        identity: str,
    ) -> AuditEvent:
        response_payload = "|".join(map(str, outcome.artifacts)) + (
            outcome.reason or ""
        )
        event = AuditEvent(
            event_type=event_type,
            counterparty_id=entry.id,
            task_id=outcome.task_id,
            request_hash=content_hash(request_payload),
            response_hash=content_hash(response_payload),
            identity=identity,
            card_version=entry.card_version,
        )
        self.events.append(event)
        return event

    def clear(self) -> None:
        self.events.clear()


audit_log = BoundaryAuditLog()
