"""Policy as code: the rules a write must pass, with a budget and a clock."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from chapter8.approvals import ApprovalBook, action_hash
from chapter8.gateway import Gateway
from chapter8.session import Session
from chapter8.settings import DATA


class Limits(BaseModel):
    version: str
    writes_per_hour: int
    changes_per_write: int
    approval_ttl_hours: int


def load_limits(path: Path | None = None) -> Limits:
    path = path or DATA / "policies" / "write-policy.yaml"
    return Limits.model_validate(yaml.safe_load(path.read_text()))


@dataclass(frozen=True)
class Decision:
    allow: bool
    rule: str


class WritePolicy:
    def __init__(
        self, gateway: Gateway, book: ApprovalBook, limits: Limits
    ) -> None:
        self.catalog = gateway.catalog
        self.registry = gateway.registry
        self.events = gateway.events
        self.clock: Callable[[], datetime] = gateway.clock
        self.book = book
        self.limits = limits
        self._lock = threading.Lock()

    def decide(
        self,
        session: Session,
        tool: str,
        arguments: dict[str, Any],
        version: int,
    ) -> Decision:
        now = self.clock()
        entry = self.catalog.entry_for(session.agent_id, tool)
        if entry is None:
            return Decision(False, "unknown tool, denied by default")
        if not self.registry.enabled(session.agent_id):
            return Decision(False, "agent is stopped")
        if entry.risk == "read":
            return Decision(True, "read-only tool in the catalog")
        digest = action_hash(tool, arguments, session.patient_id)
        problem = self.book.problem(
            digest, session.clinician, entry.approval, now
        )
        if problem:
            return Decision(False, problem)
        if arguments["record_version"] != version:
            return Decision(False, "record changed after the proposal was made")
        hour_ago = now - timedelta(hours=1)
        spent = self.events.count(session.agent_id, "write_authorized", hour_ago)
        if spent >= self.limits.writes_per_hour:
            return Decision(False, "hourly write budget is spent")
        if len(arguments["changes"]) > self.limits.changes_per_write:
            return Decision(False, "too many changes in one write")
        return Decision(True, "approved write within budget")

    def authorize(
        self,
        session: Session,
        tool: str,
        arguments: dict[str, Any],
        version: int,
    ) -> Decision:
        """Decide and record the decision as one step, so two writers cannot both pass."""
        with self._lock:
            decision = self.decide(session, tool, arguments, version)
            entry = self.catalog.entry_for(session.agent_id, tool)
            is_write = entry is not None and entry.risk != "read"
            allowed = "write_authorized" if is_write else "read_allowed"
            kind = allowed if decision.allow else "policy_denied"
            self.events.append(kind, session.agent_id, tool, decision.rule)
            return decision
