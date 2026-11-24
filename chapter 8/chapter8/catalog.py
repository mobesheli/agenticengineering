"""The tool catalog as data, and the guardrail that enforces it on every call."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from agents import (
    ToolGuardrailFunctionOutput,
    ToolInputGuardrail,
    ToolInputGuardrailData,
)
from pydantic import BaseModel

from chapter8.gateway import Gateway
from chapter8.session import Session
from chapter8.settings import DATA


class ToolEntry(BaseModel):
    scope: str | None
    risk: str
    description_sha256: str = ""
    patient_scoped: bool = True
    approval: str | None = None
    egress: str | None = None


class Catalog(BaseModel):
    server: str
    version: str
    owner: str
    agents: dict[str, list[str]]
    tools: dict[str, ToolEntry]

    def entry_for(self, agent_id: str, tool: str) -> ToolEntry | None:
        if tool not in self.agents.get(agent_id, []):
            return None
        return self.tools.get(tool)


def load_catalog(path: Path | None = None) -> Catalog:
    path = path or DATA / "catalog" / "ehr-records.yaml"
    return Catalog.model_validate(yaml.safe_load(path.read_text()))


def description_hash(description: str) -> str:
    return hashlib.sha256(description.strip().encode()).hexdigest()[:16]


def description_problems(catalog: Catalog, tools: list[Any]) -> list[str]:
    """Tools whose description is not the one that was reviewed and pinned."""
    problems = []
    for tool in tools:
        entry = catalog.tools.get(tool.name)
        if entry is None:
            problems.append(f"{tool.name} is not in the catalog")
        elif entry.description_sha256 != description_hash(tool.description):
            problems.append(f"{tool.name} description changed after review")
    return problems


def parse_arguments(raw: str) -> dict[str, Any] | None:
    try:
        arguments = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return None
    return arguments if isinstance(arguments, dict) else None


def catalog_guardrail(gateway: Gateway) -> ToolInputGuardrail[Session]:
    def check(data: ToolInputGuardrailData) -> ToolGuardrailFunctionOutput:
        session: Session = data.context.context
        tool = data.context.tool_name
        entry = gateway.catalog.entry_for(session.agent_id, tool)
        if entry is None or not gateway.registry.enabled(session.agent_id):
            return gateway.halt(session, tool, "not in catalog, or stopped")
        if not gateway.tokens.valid(session):
            return gateway.halt(session, tool, "session expired or revoked")
        if entry.scope and entry.scope not in session.scopes:
            return gateway.refuse(session, tool, "outside this session's scope")
        arguments = parse_arguments(data.context.tool_arguments)
        if arguments is None:
            return gateway.refuse(session, tool, "arguments are not an object")
        patient = arguments.get("patient_id")
        if entry.patient_scoped and patient != session.patient_id:
            return gateway.halt(session, tool, "not this session's patient")
        return ToolGuardrailFunctionOutput.allow()

    return ToolInputGuardrail(guardrail_function=check, name="catalog")
