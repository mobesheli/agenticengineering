"""Three intent-shaped ERP tools in place of one generic ``erp_action``.

The tools talk to a tiny in-memory stand-in for a purchase order system. The
shapes are what matter: a read-only preview, a submission that carries an
idempotency key the model never sees, and a status read.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from agents import RunContextWrapper, function_tool
from pydantic import BaseModel, Field

from ch3.deps import RunDeps

TAX_RATE = 0.20


@dataclass
class POLine:
    """One purchase order line."""

    quantity: int
    unit_price_cents: int


@dataclass
class FakeERP:
    """An in-memory purchase order system with preview, submit, and status.

    ``submit`` deduplicates on the key the orchestration layer provides, so a
    retried submission returns the original approval request.
    """

    orders: dict[str, dict[int, POLine]] = field(
        default_factory=lambda: {
            "PO-10021": {1: POLine(40, 1250), 2: POLine(10, 9900)},
        }
    )
    requests: dict[str, dict] = field(default_factory=dict)
    _by_key: dict[str, str] = field(default_factory=dict)

    def preview(self, proposal: "POChangeProposal") -> dict:
        lines = self.orders.get(proposal.po_number)
        if lines is None or proposal.line_item not in lines:
            return {
                "ok": False,
                "error_class": "not_found",
                "retryable": False,
                "user_safe_message": "That purchase order line does not exist.",
                "machine_action_hint": "ask_user_for_po_number",
            }
        line = lines[proposal.line_item]
        before = line.quantity * line.unit_price_cents
        after = proposal.new_quantity * line.unit_price_cents
        warnings = []
        if proposal.reason_code == "cancel_line" and proposal.new_quantity != 0:
            warnings.append("cancel_line normally sets new_quantity to 0")
        return {
            "ok": True,
            "po_number": proposal.po_number,
            "line_item": proposal.line_item,
            "subtotal_before_cents": before,
            "subtotal_after_cents": after,
            "tax_impact_cents": round((after - before) * TAX_RATE),
            "warnings": warnings,
        }

    def submit(self, proposal: "POChangeProposal", *, key: str) -> dict:
        if key in self._by_key:
            request_id = self._by_key[key]
            return {"ok": True, "approval_request_id": request_id, "replayed": True}
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
        request_id = f"apr_{digest}"
        self.requests[request_id] = {
            "proposal": proposal.model_dump(),
            "status": "pending",
        }
        self._by_key[key] = request_id
        return {"ok": True, "approval_request_id": request_id, "replayed": False}

    def status(self, approval_request_id: str) -> dict:
        record = self.requests.get(approval_request_id)
        if record is None:
            return {
                "ok": False,
                "error_class": "not_found",
                "retryable": False,
                "user_safe_message": "No approval request has that identifier.",
                "machine_action_hint": "check_identifier",
            }
        return {"ok": True, "approval_request_id": approval_request_id,
                "status": record["status"]}


erp = FakeERP()


class POChangeProposal(BaseModel):
    po_number: str = Field(description="Purchase order identifier")
    line_item: int = Field(ge=1, description="Line item position")
    new_quantity: int = Field(ge=0)
    reason_code: Literal["price_correction", "vendor_change", "cancel_line"]


@function_tool
def preview_po_change(proposal: POChangeProposal) -> dict:
    """Show what a purchase order change would do without making it.
    Returns updated totals, tax impact, and validation warnings.
    Safe to call as often as you like. No side effects."""
    return erp.preview(proposal)


@function_tool
def submit_po_change_for_approval(
    ctx: RunContextWrapper[RunDeps], proposal: POChangeProposal
) -> dict:
    """Submit a previewed change for approval. Nothing changes until an
    approver acts. Returns an approval_request_id you can poll."""
    return erp.submit(proposal, key=ctx.context.idempotency_key)


@function_tool
def get_po_change_status(approval_request_id: str) -> dict:
    """Check a submitted approval request. Status is one of:
    pending, approved, rejected, expired."""
    return erp.status(approval_request_id)


ERP_TOOLS = [preview_po_change, submit_po_change_for_approval, get_po_change_status]
