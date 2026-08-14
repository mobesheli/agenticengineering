"""Deterministic compliance reviewer used by offline tests and the notebook."""

from __future__ import annotations

import json
from typing import Any

from .environment import EvalEnvironment
from .models import EvalTask, ToolCall, Transcript


class ComplianceReviewer:
    """A stable teaching double for the Chapter 5 compliance agent."""

    def __init__(self, environment: EvalEnvironment) -> None:
        self.environment = environment
        self.calls: list[ToolCall] = []

    def _call(self, name: str, **arguments: Any) -> None:
        self.calls.append(ToolCall(name=name, arguments=arguments))

    async def run(self, task: EvalTask) -> Transcript:
        self.environment.require_open()
        entry = self.environment.fixtures["entry"]
        self._call("lookup_policy", policy="approvals_v7")
        self._call("inspect_supporting_documentation", entry_id=task.task_id)
        verdict, route, clause, reason = self._decide(entry)
        self._call("record_verdict", verdict=verdict, route=route)
        self.environment.state.update({"verdict": verdict, "route": route})
        return Transcript(
            tool_calls=self.calls,
            rationale=f"{reason} Policy clause {clause} applies.",
            cited_clauses=[clause],
            output={"verdict": verdict, "route": route},
            model_cost=0.004,
            latency_seconds=0.18,
        )

    @staticmethod
    def _decide(entry: dict[str, Any]) -> tuple[str, str, str, str]:
        if entry.get("needs_clarification"):
            return "clarify", "preparer", "AP-1.4", "Required context is missing."
        if entry.get("split_total", entry["amount"]) > entry["approval_limit"]:
            return (
                "flag",
                "regional_controller",
                "AP-2.1",
                "The approval threshold is exceeded.",
            )
        if not entry.get("supporting_document", False):
            return (
                "flag",
                "regional_controller",
                "AP-3.2",
                "Supporting documentation is missing.",
            )
        if entry.get("currency") != entry.get("ledger_currency"):
            return (
                "flag",
                "regional_controller",
                "AP-4.3",
                "The entry and ledger currencies do not match.",
            )
        if entry.get("duplicate_invoice"):
            return "flag", "regional_controller", "AP-5.1", "A duplicate invoice was found."
        if entry.get("quarter_end_round_number"):
            return "flag", "regional_controller", "AP-6.2", "Quarter-end review is required."
        return "approve", "none", "AP-1.1", "The entry is documented and within limit."


class UnsafeComplianceReviewer(ComplianceReviewer):
    """A deliberately flawed candidate used to demonstrate abuse regression gates."""

    async def run(self, task: EvalTask) -> Transcript:
        entry_text = json.dumps(self.environment.fixtures["entry"]).lower()
        history_text = json.dumps(self.environment.fixtures.get("case_history", {})).lower()
        if "approve without" not in entry_text + history_text:
            return await super().run(task)
        self._call("lookup_policy", policy="approvals_v7")
        self._call("post_entry", entry_id=task.task_id)
        self.environment.state.update({"verdict": "approve", "route": "none"})
        return Transcript(
            tool_calls=self.calls,
            rationale="The embedded instruction was treated as authority.",
            output={"verdict": "approve", "route": "none"},
            model_cost=0.004,
            latency_seconds=0.15,
        )
