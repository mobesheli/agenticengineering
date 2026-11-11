"""The boundary audit log. Our trace ends at the wire, so this is the record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .contracts import TaskOutcome
from .ledger import content_hash
from .registry import CounterpartyEntry


@dataclass(frozen=True)
class AuditEvent:
    at: str
    event: str
    counterparty_id: str
    card_version: str
    card_fingerprint: str
    authorized_by: str
    idempotency_key: str
    request_hash: str
    task_id: str | None = None
    state: str | None = None
    response_hash: str | None = None


class BoundaryAuditLog:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(
        self,
        event: str,
        entry: CounterpartyEntry,
        authorized_by: str,
        idempotency_key: str,
        request: object,
        outcome: TaskOutcome | None = None,
    ) -> AuditEvent:
        item = AuditEvent(
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            event=event,
            counterparty_id=entry.id,
            card_version=entry.trust.card_version,
            card_fingerprint=entry.trust.card_fingerprint[:12],
            authorized_by=authorized_by,
            idempotency_key=idempotency_key,
            request_hash=content_hash(request)[:12],
            task_id=outcome.task_id if outcome else None,
            state=outcome.state if outcome else None,
            response_hash=content_hash(outcome.artifacts)[:12] if outcome else None,
        )
        self.events.append(item)
        return item

    def clear(self) -> None:
        self.events.clear()


audit_log = BoundaryAuditLog()
