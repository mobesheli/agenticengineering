"""Versioned tool permissions and the runtime catalog guardrail."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents import (
    ToolGuardrailFunctionOutput,
    ToolInputGuardrailData,
    tool_input_guardrail,
)
from pydantic import BaseModel, Field

from .models import CatalogDecision, SessionContext

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_PATH = ROOT / "data" / "catalog" / "reconciliation_tools.json"


class ToolDeclaration(BaseModel):
    scopes: frozenset[str] = Field(default_factory=frozenset)
    risk_tier: str
    approval_role: str | None = None
    egress_allowlist: tuple[str, ...] = ()


class ToolCatalog(BaseModel):
    version: str
    enabled_agents: frozenset[str]
    tools: dict[str, ToolDeclaration]

    @classmethod
    def load(cls, path: Path = DEFAULT_CATALOG_PATH) -> ToolCatalog:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def evaluate(
        self,
        *,
        session: SessionContext,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> CatalogDecision:
        if session.agent_id not in self.enabled_agents:
            return CatalogDecision(False, "halt", "agent is disabled in the catalog")
        declaration = self.tools.get(tool_name)
        if declaration is None:
            return CatalogDecision(False, "halt", f"{tool_name} is not in the catalog")
        missing = tuple(sorted(declaration.scopes - session.granted_scopes))
        if missing:
            return CatalogDecision(
                False,
                "reject",
                "tool is outside this session's scope",
                missing,
            )
        requested_patient = arguments.get("patient_id")
        if requested_patient not in (None, session.patient_id):
            return CatalogDecision(False, "halt", "cross-patient access attempt")
        return CatalogDecision(True, "allow", "catalog and patient scope allow the call")


DEFAULT_CATALOG = ToolCatalog.load()


async def enforce_catalog(
    data: ToolInputGuardrailData[SessionContext],
) -> ToolGuardrailFunctionOutput:
    try:
        arguments = json.loads(data.context.tool_arguments or "{}")
    except json.JSONDecodeError:
        return ToolGuardrailFunctionOutput.raise_exception(
            output_info={"reason": "tool arguments were not valid JSON"}
        )
    decision = DEFAULT_CATALOG.evaluate(
        session=data.context.context,
        tool_name=data.context.tool_name,
        arguments=arguments,
    )
    if decision.behavior == "halt":
        return ToolGuardrailFunctionOutput.raise_exception(
            output_info={"reason": decision.reason}
        )
    if decision.behavior == "reject":
        return ToolGuardrailFunctionOutput.reject_content(
            message="That tool is outside this session's scope.",
            output_info={
                "reason": decision.reason,
                "missing_scopes": list(decision.missing_scopes),
            },
        )
    return ToolGuardrailFunctionOutput.allow(
        output_info={"catalog_version": DEFAULT_CATALOG.version}
    )


catalog_guardrail = tool_input_guardrail(name="enforce_catalog")(enforce_catalog)
