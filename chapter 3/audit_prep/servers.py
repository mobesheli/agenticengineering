"""The three MCP servers behind the audit-prep agent.

The data server and the policy server are read-only. The evidence store is
where the side-effect boundary lives: a preview, a hash-deduplicated artifact
write, and the single publish that the host marks as needing approval.
"""

from __future__ import annotations

from typing import Literal

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from audit_prep.fakes import FakeEvidenceStore, FakeFinanceData, FakePolicy
from audit_prep.inprocess import InProcessMCPServer

finance_data = FakeFinanceData()
policy = FakePolicy()
evidence = FakeEvidenceStore()


# Data server: parameterized, bounded reads.

data_app = MCPServer("finance-data")


class TrialBalanceQuery(BaseModel):
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    entity: str = Field(min_length=2)
    materiality_threshold: int = Field(ge=0)


@data_app.tool()
def get_trial_balance_snapshot(query: TrialBalanceQuery) -> dict:
    """Return a trial balance snapshot for the named period and entity,
    filtered to accounts above the materiality threshold.
    Read-only. Safe to call repeatedly."""
    return finance_data.snapshot(**query.model_dump())


@data_app.tool()
def get_journal_entries(
    period: str, above_amount: int, cursor: int = 0, page_size: int = 3
) -> dict:
    """Return journal entries at or above an amount for a period, one page at
    a time. Pass next_cursor from the previous page to continue. Read-only."""
    return finance_data.journal_entries(
        period=period, above_amount=above_amount, cursor=cursor, page_size=page_size
    )


@data_app.tool()
def check_existing_evidence_bundle(control_id: str, period: str) -> dict:
    """Report whether an evidence bundle is already on record for a control
    and period, so work is not repeated. Read-only."""
    key = f"{control_id}:{period}"
    return {"ok": True, "exists": key in finance_data.bundles_on_record}


# Policy server: typed reads against the reporting reference data.

policy_app = MCPServer("reporting-policy")


@policy_app.tool()
def get_reporting_requirements(
    jurisdiction: Literal["uk", "us", "eu"], report_type: str, effective_date: str
) -> dict:
    """Return the structured reporting requirements that applied in a
    jurisdiction on the effective date, with the policy version. Read-only."""
    return policy.requirements(
        jurisdiction=jurisdiction, report_type=report_type, effective_date=effective_date
    )


# Evidence store: preview, deduplicated write, gated publish.

evidence_app = MCPServer("evidence-store")


@evidence_app.tool()
def preview_evidence_bundle(control_id: str, period: str) -> dict:
    """Return the calculated structure of an evidence bundle for a control and
    period, as a draft, without publishing anything. Safe to call repeatedly."""
    return evidence.preview_bundle(control_id=control_id, period=period)


@evidence_app.tool()
def write_evidence_artifact(bundle_id: str, kind: str, content: str) -> dict:
    """Write one artifact into a draft bundle. The artifact's content hash
    prevents duplicate writes; rewriting identical content is a no-op."""
    return evidence.write_artifact(bundle_id=bundle_id, kind=kind, content=content)


@evidence_app.tool()
def publish_evidence_bundle(bundle_id: str, content_hash: str) -> dict:
    """Publish a draft bundle. Irreversible. Requires approval, and the
    content_hash must match the bundle as it stands or the publish is refused."""
    return evidence.publish(bundle_id=bundle_id, content_hash=content_hash)


def data_server() -> InProcessMCPServer:
    """The finance data server, read-only."""
    return InProcessMCPServer(data_app)


def policy_server() -> InProcessMCPServer:
    """The reporting policy server, read-only."""
    return InProcessMCPServer(policy_app)


def evidence_store() -> InProcessMCPServer:
    """The evidence store, with the publish tool marked for approval.

    ``require_approval`` is the same keyword ``MCPServerStreamableHttp`` takes;
    the in-process adapter inherits it from the SDK's ``MCPServer`` base class.
    The approval requirement is a host decision, made here in the registry
    rather than in the agent's instructions.
    """
    return InProcessMCPServer(
        evidence_app, require_approval={"publish_evidence_bundle": "always"}
    )
