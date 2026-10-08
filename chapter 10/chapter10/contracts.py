"""Deterministic tool-contract enforcement and optional Agents SDK hook."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import load_model
from .models import ToolContract

try:
    from agents import RunHooks
except (
    ImportError
):  # pragma: no cover - the deterministic companion works without live SDK use

    class RunHooks:  # type: ignore[no-redef]
        """Small compatibility base when the optional SDK is not installed."""


@dataclass(frozen=True)
class ContractDecision:
    allowed: bool
    reason: str
    trace_note: str


class ContractEnforcer:
    def __init__(self, contracts: list[ToolContract]) -> None:
        self._contracts = {contract.tool: contract for contract in contracts}

    @classmethod
    def from_directory(cls, directory: Path) -> ContractEnforcer:
        contracts = [
            load_model(path, ToolContract) for path in sorted(directory.glob("*.yaml"))
        ]
        if not contracts:
            raise ValueError(f"no tool contracts found in {directory}")
        return cls(contracts)

    def check(self, tool_name: str, operation: str) -> ContractDecision:
        contract = self._contracts.get(tool_name)
        if contract is None:
            return ContractDecision(
                False, f"{tool_name}: no contract, refused", "contract:none"
            )
        note = f"contract:{contract.tool}@{contract.version}"
        if operation in contract.never or operation not in contract.allow:
            return ContractDecision(
                False,
                f"{tool_name}.{operation}: outside contract",
                note,
            )
        return ContractDecision(True, "allowed", note)

    def enforce(self, tool_name: str, operation: str) -> ContractDecision:
        decision = self.check(tool_name, operation)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return decision


class ContractHook(RunHooks):
    """SDK-shaped hook that keeps the permission decision outside the model."""

    def __init__(self, enforcer: ContractEnforcer) -> None:
        self.enforcer = enforcer

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        del agent
        arguments = getattr(context, "tool_arguments", {}) or {}
        operation = arguments.get("operation", "")
        decision = self.enforcer.enforce(tool.name, operation)
        run_context = getattr(context, "context", None)
        trace_note = getattr(run_context, "trace_note", None)
        if callable(trace_note):
            trace_note(decision.trace_note)
