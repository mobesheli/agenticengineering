"""The agent registry: every agent, its owner, its risk tier, and its stop state."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from chapter8.settings import DATA


class AgentEntry(BaseModel):
    agent_id: str
    owner: str
    purpose: str
    risk_tier: str
    autonomy: str
    enabled: bool = True
    stopped_by: str | None = None
    stopped_at: datetime | None = None
    stop_reason: str | None = None


class Registry:
    def __init__(self, entries: list[AgentEntry]) -> None:
        self._entries = {entry.agent_id: entry for entry in entries}

    @classmethod
    def load(cls, path: Path | None = None) -> Registry:
        path = path or DATA / "registry.yaml"
        rows = yaml.safe_load(path.read_text())["agents"]
        return cls([AgentEntry.model_validate(row) for row in rows])

    def entry(self, agent_id: str) -> AgentEntry | None:
        return self._entries.get(agent_id)

    def enabled(self, agent_id: str) -> bool:
        entry = self._entries.get(agent_id)
        return entry is not None and entry.enabled

    def stop(self, agent_id: str, by: str, reason: str, now: datetime) -> None:
        entry = self._entries[agent_id]
        entry.enabled = False
        entry.stopped_by, entry.stopped_at, entry.stop_reason = by, now, reason

    def restore(self, agent_id: str) -> None:
        entry = self._entries[agent_id]
        entry.enabled = True
        entry.stopped_by = entry.stopped_at = entry.stop_reason = None
