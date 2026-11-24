"""The emergency stop. It works on things the agent depends on, not on the agent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from chapter8.harness import Harness


@dataclass
class StopReport:
    stopped: list[str]
    tokens_revoked: int
    approvals_voided: int
    left_behind: list[str]


def emergency_stop(
    harness: Harness, agents: list[str], by: str, reason: str
) -> StopReport:
    now = harness.clock()
    revoked = 0
    for agent_id in agents:
        harness.registry.stop(agent_id, by, reason, now)
        revoked += harness.tokens.revoke_agent(agent_id)
        harness.events.append(
            "agent_stopped", agent_id, "stop", f"{by}: {reason}"
        )
    voided = harness.book.void_all()
    hour_ago = now - timedelta(hours=1)
    recent = [
        event.detail
        for event in harness.events.of_kind("write_executed")
        if event.agent_id in agents and event.at >= hour_ago
    ]
    return StopReport(agents, revoked, voided, recent)
