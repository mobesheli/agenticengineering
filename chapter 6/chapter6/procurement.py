"""The code-led sourcing spine: fan out, compare, approve, commit."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from .audit import audit_log
from .contracts import (
    ORDER_SKILL,
    Approval,
    CommitResult,
    FastenerQuote,
    PurchaseOrder,
    QuoteToolResult,
)
from .remote import Delegation, request_supplier_quote, send_task


async def gather_quotes(
    via: Delegation, bom: dict[str, Any], commodity: str
) -> list[QuoteToolResult]:
    suppliers = via.registry.approved_for(commodity)
    requests = [request_supplier_quote(via, s.id, bom) for s in suppliers]
    return list(await asyncio.gather(*requests))


def compare_quotes(
    results: list[QuoteToolResult], needed_in_days: int
) -> QuoteToolResult:
    in_time = [r for r in results if r.ok and r.quote.lead_time_days <= needed_in_days]
    if not in_time:
        raise ValueError("no supplier can meet the delivery date")
    return min(in_time, key=lambda r: (r.quote.unit_price, r.quote.lead_time_days))


def propose_order(
    po_number: str, supplier_id: str, quote: FastenerQuote, quantity: int, due: date
) -> PurchaseOrder:
    return PurchaseOrder(
        po_number=po_number,
        supplier_id=supplier_id,
        quote_id=quote.quote_id,
        quantity=quantity,
        unit_price=quote.unit_price,
        currency=quote.currency,
        delivery_date=due,
    )


async def commit_purchase_order(
    via: Delegation, po: PurchaseOrder, approval: Approval
) -> CommitResult:
    if not approval.authorizes(po, today=date.today()):
        return CommitResult(
            committed=False, reason="approval_does_not_cover_this_order"
        )
    entry = via.registry.require(po.supplier_id)
    payload = po.to_payload(approval.reference)
    buyer = f"buyer/{approval.approved_by}"
    audit_log.record("commit_intent", entry, buyer, po.po_number, payload)
    try:
        outcome = await asyncio.wait_for(
            send_task(entry, via.http, ORDER_SKILL, payload, po.po_number),
            entry.sla_seconds,
        )
    except Exception as broken:
        unknown = f"outcome_unknown:{type(broken).__name__}"
        return CommitResult(committed=False, reason=unknown)
    audit_log.record("commit_outcome", entry, buyer, po.po_number, payload, outcome)
    if outcome.state != "completed":
        reason = outcome.reason or outcome.state
        return CommitResult(committed=False, reason=reason, task_id=outcome.task_id)
    confirmation = outcome.artifacts[0]["confirmation"]
    return CommitResult(
        committed=True, confirmation=confirmation, task_id=outcome.task_id
    )
