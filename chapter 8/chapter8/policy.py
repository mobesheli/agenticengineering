"""Temporal write policy backed by an append-only event history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .models import PolicyDecision


@dataclass(frozen=True)
class SecurityEvent:
    agent_id: str
    event_type: str
    occurred_at: datetime
    action_hash: str | None = None
    details: tuple[tuple[str, str], ...] = ()


class EventHistory:
    def __init__(self) -> None:
        self._events: list[SecurityEvent] = []

    @property
    def events(self) -> tuple[SecurityEvent, ...]:
        return tuple(self._events)

    def append(self, event: SecurityEvent) -> None:
        self._events.append(event)

    def has(self, agent_id: str, event_type: str, action_hash: str) -> bool:
        return any(
            event.agent_id == agent_id
            and event.event_type == event_type
            and event.action_hash == action_hash
            for event in self._events
        )

    def count(self, agent_id: str, event_type: str, *, since: datetime) -> int:
        return sum(
            event.agent_id == agent_id
            and event.event_type == event_type
            and event.occurred_at >= since
            for event in self._events
        )


class WritePolicy:
    def __init__(self, history: EventHistory, max_writes_per_hour: int = 5) -> None:
        if max_writes_per_hour < 1:
            raise ValueError("max_writes_per_hour must be positive")
        self.history = history
        self.max_writes = max_writes_per_hour

    def evaluate(
        self,
        agent_id: str,
        tool: str,
        args: dict[str, Any],
        now: datetime,
    ) -> PolicyDecision:
        if tool != "write_reconciliation":
            return PolicyDecision(True, "read-only tool")
        digest = str(args.get("action_hash", ""))
        if not digest or not self.history.has(agent_id, "approval_granted", digest):
            return PolicyDecision(False, "no approval on record for this action")
        since = now - timedelta(hours=1)
        if self.history.count(agent_id, "write_executed", since=since) >= self.max_writes:
            return PolicyDecision(
                False,
                f"write budget of {self.max_writes} per hour spent",
            )
        if len(args.get("changes", [])) > 10:
            return PolicyDecision(False, "more than ten changes in a single write")
        return PolicyDecision(True, "approved write within budget")
