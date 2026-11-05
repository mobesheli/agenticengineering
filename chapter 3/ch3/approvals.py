"""The approval gate: where the human says yes, or no.

The loop here is the orchestration side of the SDK's human-in-the-loop flow.
Run the agent; while the result carries interruptions, take the run's state,
record a decision on each pending call, and run again from that state. The
decision lives in this layer. The model never holds a credential.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from agents import Agent, RunResult, Runner
from agents.items import ToolApprovalItem

from ch3.deps import RunDeps


@dataclass(frozen=True)
class ApprovalDecision:
    """What a reviewer decided and, when the answer is no, why."""

    approved: bool
    reason: str = ""


class ApprovalService(Protocol):
    """Anything that can decide on a pending tool call."""

    async def decide(self, item: ToolApprovalItem) -> ApprovalDecision: ...


@dataclass
class ScriptedReviewer:
    """A reviewer with its mind made up, for drills and tests.

    Production replaces this with a queue and a person. The interface is the
    same: one interruption in, one decision out.
    """

    approve: bool
    reason: str = ""
    seen: list[ToolApprovalItem] = field(default_factory=list)

    async def decide(self, item: ToolApprovalItem) -> ApprovalDecision:
        self.seen.append(item)
        return ApprovalDecision(approved=self.approve, reason=self.reason)


def pending_arguments(item: ToolApprovalItem) -> dict[str, Any]:
    """Return the arguments of a pending call as a dictionary."""
    raw = item.arguments
    if raw is None:
        return {}
    if isinstance(raw, str):
        return json.loads(raw)
    return dict(raw)


async def run_with_approvals(
    refund_agent: Agent[RunDeps],
    task: str,
    deps: RunDeps,
    approvals: ApprovalService,
) -> RunResult:
    """Run an agent to completion, routing every interruption through ``approvals``."""
    result = await Runner.run(refund_agent, task, context=deps)
    while result.interruptions:
        state = result.to_state()
        for item in result.interruptions:
            decision = await approvals.decide(item)   # a human, eventually
            if decision.approved:
                state.approve(item)
            else:
                state.reject(item, rejection_message=decision.reason)
        result = await Runner.run(refund_agent, state)
    return result
