"""The audit-evidence assembler agent and its output guardrail."""

from __future__ import annotations

from typing import Any

from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, output_guardrail
from agents.mcp import MCPServer
from agents.models.interface import Model

from audit_prep import servers
from audit_prep.models import AuditRunContext, EvidenceBundleStatus

EVIDENCE_AGENT_INSTRUCTIONS = """You assemble audit evidence bundles for a control owner.

Work in this order. Pull the trial balance snapshot and a sample of journal
entries above the materiality threshold from the data server. Pull the reporting
requirements for the jurisdiction and period from the policy server; never rely
on your own memory of the rules. Create a draft bundle, write one artifact per
required section, and only then call publish_evidence_bundle with the bundle id
and the content hash you were given. If a tool returns ok=false, read
machine_action_hint and do what it says. Report the bundle status when you stop.
"""


@output_guardrail
async def bundle_completeness_check(
    ctx: RunContextWrapper[AuditRunContext],
    agent: Agent[Any],
    output: EvidenceBundleStatus,
) -> GuardrailFunctionOutput:
    """Trip when a bundle reported as published is missing a required artifact.

    The required list comes from the policy server, pinned to the request's
    jurisdiction, not from anything the model remembers.
    """
    request = ctx.context.request
    rules = servers.policy.requirements(
        jurisdiction=request.jurisdiction,
        report_type="liquidity",
        effective_date=f"{request.period}-end",
    )
    required = set(rules.get("required_artifacts", []))
    present = set(servers.evidence.artifact_kinds(output.bundle_id))
    missing = sorted(required - present)
    return GuardrailFunctionOutput(
        output_info={"required": sorted(required), "missing": missing},
        tripwire_triggered=output.status == "published" and bool(missing),
    )


def build_agent(
    data_server: MCPServer,
    policy_server: MCPServer,
    evidence_store: MCPServer,
    *,
    model: Model | str | None = None,
) -> Agent[AuditRunContext]:
    """Create the agent inside the servers' lifecycle so its tools exist when it does."""
    agent = Agent(
        name="audit-evidence-assembler",
        instructions=EVIDENCE_AGENT_INSTRUCTIONS,
        mcp_servers=[data_server, policy_server, evidence_store],
        output_type=EvidenceBundleStatus,
        output_guardrails=[bundle_completeness_check],
    )
    if model is not None:
        agent.model = model
    return agent
