"""Tool contracts: what each tool server may be asked to do, checked before the call."""

from __future__ import annotations

from pathlib import Path

import yaml
from agents import (
    ToolGuardrailFunctionOutput,
    ToolInputGuardrail,
    ToolInputGuardrailData,
)
from pydantic import BaseModel

from chapter10.platform import Platform


class Contract(BaseModel):
    tool: str
    server: str
    version: str
    allow: list[str]
    never: list[str]
    egress: list[str]
    credential: str


def load_contracts(folder: Path) -> dict[str, Contract]:
    files = sorted(folder.glob("*.yaml"))
    contracts = [Contract.model_validate(yaml.safe_load(f.read_text())) for f in files]
    return {contract.tool: contract for contract in contracts}


def contract_problems(contracts: dict[str, Contract]) -> list[str]:
    """The rules the pipeline enforces on every contract, in every gate mode."""
    problems = []
    for name, contract in contracts.items():
        if contract.credential != "agent-identity":
            problems.append(f"{name}: must use the agent's own identity")
        if not contract.egress:
            problems.append(f"{name}: declares no egress allowlist")
        if set(contract.allow) & set(contract.never):
            problems.append(f"{name}: an operation is both allowed and forbidden")
    return problems


def contract_guardrail(platform: Platform, server: str) -> ToolInputGuardrail:
    def check(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
        operation = data.context.tool_name
        contract = platform.contracts.get(server)
        if contract is None:
            reason = f"{server}: no contract, refused"
        elif operation in contract.never or operation not in contract.allow:
            reason = f"{server}.{operation}: outside contract {contract.version}"
        else:
            platform.note("contract", f"{server}@{contract.version} {operation}")
            return ToolGuardrailFunctionOutput.allow()
        platform.note("policy_denied", reason)
        return ToolGuardrailFunctionOutput.reject_content(reason)

    return ToolInputGuardrail(guardrail_function=check, name=server)
