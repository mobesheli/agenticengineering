"""Agent inventory and a gateway-enforced stop control."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


class AgentStoppedError(RuntimeError):
    pass


@dataclass
class AgentEntry:
    agent_id: str
    owner: str
    risk_tier: str
    enabled: bool = True
    stopped_at: datetime | None = None
    stop_reason: str | None = None


class AgentRegistry:
    def __init__(self, entries: list[AgentEntry] | None = None) -> None:
        initial = entries or [
            AgentEntry(
                agent_id="medication-reconciliation-agent",
                owner="clinical-safety-lead",
                risk_tier="acts_with_approval",
            )
        ]
        self._entries = {entry.agent_id: entry for entry in initial}

    def require_enabled(self, agent_id: str) -> AgentEntry:
        entry = self._entries.get(agent_id)
        if entry is None:
            raise AgentStoppedError("agent is not registered")
        if not entry.enabled:
            raise AgentStoppedError(entry.stop_reason or "agent is stopped")
        return entry

    def stop(self, agent_id: str, *, reason: str, now: datetime) -> None:
        entry = self._entries[agent_id]
        entry.enabled = False
        entry.stopped_at = now
        entry.stop_reason = reason

    def restore(self, agent_id: str) -> None:
        entry = self._entries[agent_id]
        entry.enabled = True
        entry.stopped_at = None
        entry.stop_reason = None

    def snapshot(self) -> dict[str, dict[str, object]]:
        return {
            agent_id: {
                "owner": entry.owner,
                "risk_tier": entry.risk_tier,
                "enabled": entry.enabled,
                "stopped_at": entry.stopped_at.isoformat() if entry.stopped_at else None,
                "stop_reason": entry.stop_reason,
            }
            for agent_id, entry in sorted(self._entries.items())
        }
