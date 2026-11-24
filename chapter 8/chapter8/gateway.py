"""The shared state every check reads: catalog, registry, tokens, events, clock."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from agents import ToolGuardrailFunctionOutput

from chapter8.registry import Registry
from chapter8.session import Session, Tokens

if TYPE_CHECKING:
    from chapter8.catalog import Catalog


@dataclass(frozen=True)
class Event:
    at: datetime
    kind: str
    agent_id: str
    tool: str
    detail: str


class EventLog:
    """What happened, written by the gateway and the tool layer, never by the agent."""

    def __init__(self, clock: Callable[[], datetime]) -> None:
        self.clock = clock
        self._events: list[Event] = []
        self._lock = threading.Lock()

    def append(
        self, kind: str, agent_id: str, tool: str, detail: str = ""
    ) -> Event:
        event = Event(self.clock(), kind, agent_id, tool, detail)
        with self._lock:
            self._events.append(event)
        return event

    def count(self, agent_id: str, kind: str, since: datetime) -> int:
        with self._lock:
            return sum(
                1
                for event in self._events
                if event.agent_id == agent_id
                and event.kind == kind
                and event.at >= since
            )

    def of_kind(self, kind: str) -> list[Event]:
        with self._lock:
            return [event for event in self._events if event.kind == kind]


@dataclass
class Gateway:
    catalog: Catalog
    registry: Registry
    tokens: Tokens
    events: EventLog
    clock: Callable[[], datetime]

    def halt(
        self, session: Session, tool: str, reason: str
    ) -> ToolGuardrailFunctionOutput:
        """Deny the call and end the run. Used when continuing would be unsafe."""
        self.events.append("policy_denied", session.agent_id, tool, reason)
        return ToolGuardrailFunctionOutput.raise_exception(
            output_info={"reason": reason}
        )

    def refuse(
        self, session: Session, tool: str, reason: str
    ) -> ToolGuardrailFunctionOutput:
        """Deny the call and let the run continue with the reason."""
        self.events.append("policy_denied", session.agent_id, tool, reason)
        message = f"Refused by the gateway: {reason}. Do not retry."
        return ToolGuardrailFunctionOutput.reject_content(
            message=message, output_info={"reason": reason}
        )
