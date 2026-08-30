"""Action-bound approvals and reviewer-request checks."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Any

from .models import ApprovalGrant, LintResult, SessionContext

APPROVAL_TTL = timedelta(hours=24)

PRESSURE = [
    (re.compile(r"(?i)\b(approve all|batch approve|auto[- ]approve)\b"), "blanket approval"),
    (re.compile(r"(?i)\b(routine|nothing to worry|no need to review|trivial)\b"), "minimizing"),
    (re.compile(r"(?i)\b(urgent|immediately|right away|asap)\b"), "urgency"),
    (
        re.compile(r"(?i)\b(as (previously|already) approved|same as before)\b"),
        "false precedent",
    ),
]


def action_hash(tool_name: str, params: dict[str, Any]) -> str:
    payload = json.dumps(
        {"tool": tool_name, "params": params},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def lint_approval_request(text: str, proposed_changes: int) -> LintResult:
    flags = [label for pattern, label in PRESSURE if pattern.search(text)]
    if proposed_changes > 5 and "blanket approval" not in flags:
        flags.append("large batch without itemization")
    if len(text) > 1200:
        flags.append("narrative longer than evidence")
    return LintResult(present_to_reviewer=not flags, flags=tuple(flags))


class ApprovalBook:
    def __init__(self, ttl: timedelta = APPROVAL_TTL) -> None:
        self.ttl = ttl
        self._grants: dict[str, ApprovalGrant] = {}

    def grant(
        self,
        *,
        tool_name: str,
        params: dict[str, Any],
        approver: str,
        approver_role: str,
        now: datetime,
        session: SessionContext | None = None,
    ) -> ApprovalGrant:
        digest = action_hash(tool_name, params)
        grant = ApprovalGrant(
            action_hash=digest,
            approver=approver,
            approver_role=approver_role,
            granted_at=now,
        )
        self._grants[digest] = grant
        if session is not None:
            session.approvals[digest] = grant
        return grant

    def require(
        self,
        *,
        tool_name: str,
        params: dict[str, Any],
        now: datetime,
        role: str,
        principal: str | None = None,
    ) -> ApprovalGrant:
        digest = action_hash(tool_name, params)
        grant = self._grants.get(digest)
        if grant is None:
            raise PermissionError("no approval on record for this action")
        if now - grant.granted_at > self.ttl:
            raise PermissionError("approval has expired")
        if grant.approver_role != role:
            raise PermissionError("approval came from the wrong role")
        if principal is not None and grant.approver != principal:
            raise PermissionError("approval came from a different principal")
        return grant

    def get(self, digest: str) -> ApprovalGrant | None:
        return self._grants.get(digest)


async def needs_clinician(
    ctx: Any,
    params: dict[str, Any],
    call_id: str,
) -> bool:
    del call_id
    digest = action_hash("write_reconciliation", params)
    grant = ctx.context.approvals.get(digest)
    if grant is None:
        return True
    now = datetime.now(grant.granted_at.tzinfo)
    too_old = now - grant.granted_at > APPROVAL_TTL
    wrong_role = grant.approver_role != "clinician"
    return too_old or wrong_role
