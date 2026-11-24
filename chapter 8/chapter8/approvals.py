"""Approvals bound to one exact action, from one person, for a limited time."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


def action_hash(tool: str, arguments: dict[str, Any], patient_id: str) -> str:
    action = {"tool": tool, "arguments": arguments, "patient": patient_id}
    canonical = json.dumps(action, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True)
class Grant:
    digest: str
    approver: str
    role: str
    granted_at: datetime


class ApprovalBook:
    def __init__(self, ttl: timedelta = timedelta(hours=24)) -> None:
        self.ttl = ttl
        self._grants: dict[str, Grant] = {}

    def grant(
        self, digest: str, approver: str, role: str, now: datetime
    ) -> Grant:
        self._grants[digest] = Grant(digest, approver, role, now)
        return self._grants[digest]

    def problem(self, digest: str, signer: str, role: str, now: datetime) -> str:
        grant = self._grants.get(digest)
        if grant is None:
            return "no approval for this exact action"
        if now - grant.granted_at > self.ttl:
            return "approval has expired"
        if grant.role != role or grant.approver != signer:
            return "approval is not from this clinician"
        return ""

    def approver(self, digest: str) -> str | None:
        grant = self._grants.get(digest)
        return grant.approver if grant else None

    def spend(self, digest: str) -> None:
        """An approval authorizes one execution. Using it removes it."""
        self._grants.pop(digest, None)

    def void_all(self) -> int:
        count = len(self._grants)
        self._grants.clear()
        return count
