"""The code-led supply-chain capstone from the end of Chapter 6."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from .audit import audit_log
from .contracts import (
    Approval,
    CommitResult,
    FastenerQuote,
    PurchaseOrder,
    QuoteToolResult,
)
from .registry import COUNTERPARTIES, CounterpartyEntry
from .remote import ScriptedSupplierClient, request_supplier_quote


def configure_demo_counterparties() -> dict[str, ScriptedSupplierClient]:
    """Reset the global registry to the two approved suppliers in the chapter."""

    COUNTERPARTIES.clear()
    clients = {
        "nordbolt": ScriptedSupplierClient(
            "nordbolt", unit_price=2.62, lead_time_days=28
        ),
        "rivetridge": ScriptedSupplierClient(
            "rivetridge", unit_price=2.74, lead_time_days=24
        ),
    }
    for supplier_id, client in clients.items():
        COUNTERPARTIES.register(
            CounterpartyEntry(
                id=supplier_id,
                display_name=supplier_id.title(),
                commodity_codes={"custom-brackets", "industrial-fasteners"},
                client_factory=lambda client=client: client,
                card_version="1.0.0",
                contract_reference=f"MSA-{supplier_id.upper()}-2026",
                approved_by="procurement-security-board",
                supplier_score=0.96 if supplier_id == "nordbolt" else 0.91,
            )
        )
    return clients


async def gather_quotes(bom_json: str, commodity: str) -> list[QuoteToolResult]:
    suppliers = COUNTERPARTIES.approved_for(commodity)
    requests = [
        request_supplier_quote(supplier_id=s.id, bom_json=bom_json) for s in suppliers
    ]
    results = await asyncio.gather(*requests)
    return [result for result in results if result.ok]


def compare_quotes(results: Iterable[QuoteToolResult]) -> FastenerQuote:
    """Use plain code for the declared price/lead-time comparison."""

    quotes = [result.quote for result in results if result.ok and result.quote]
    if not quotes:
        raise ValueError("no successful quotes to compare")
    return min(quotes, key=lambda quote: (quote.unit_price, quote.lead_time_days))


async def commit_purchase_order(po: PurchaseOrder, approval: Approval) -> CommitResult:
    if not approval.authorizes(po):
        return CommitResult(committed=False, reason="approval_does_not_authorize_order")
    entry = COUNTERPARTIES.require(po.supplier_id)
    payload = po.to_signed_payload(approval.reference)
    outcome = await entry.client().send_task(
        skill="accept-order",
        payload=payload,
        idempotency_key=po.po_number,
    )
    terminal = await outcome.wait_terminal(timeout_seconds=entry.sla_seconds)
    await audit_log.record_exchange(
        event_type="commitment",
        entry=entry,
        request_payload=payload,
        outcome=terminal,
        identity=f"buyer/{approval.approved_by}",
    )
    if terminal.state != "completed":
        return CommitResult(committed=False, reason=terminal.state)
    confirmation = str(terminal.artifacts[0]["confirmation"])
    return CommitResult(committed=True, confirmation=confirmation)


configure_demo_counterparties()
