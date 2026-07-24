from __future__ import annotations

from datetime import date

import pytest

from chapter6.audit import audit_log
from chapter6.contracts import Approval, BillOfMaterials, BomLine, PurchaseOrder
from chapter6.procurement import (
    commit_purchase_order,
    compare_quotes,
    configure_demo_counterparties,
    gather_quotes,
)


@pytest.mark.asyncio
async def test_supply_chain_fanout_compare_approve_and_commit() -> None:
    clients = configure_demo_counterparties()
    audit_log.clear()
    bom = BillOfMaterials(
        commodity="custom-brackets",
        requested_delivery_date=date(2026, 9, 1),
        line_items=[BomLine(sku="CB-42", description="custom bracket", quantity=2_000)],
    )
    results = await gather_quotes(bom.model_dump_json(), bom.commodity)
    winner = compare_quotes(results)
    assert len(results) == 2
    assert winner.supplier_id == "nordbolt"

    po = PurchaseOrder(
        po_number="PO-2026-0042",
        supplier_id=winner.supplier_id,
        quote_id=winner.quote_id,
        quantity=bom.total_units,
        unit_price=winner.unit_price,
        currency=winner.currency,
        delivery_date=bom.requested_delivery_date,
    )
    approval = Approval(
        reference="APR-0042",
        approved_by="alex.buyer",
        po_number=po.po_number,
        maximum_amount=po.total_value,
    )
    first = await commit_purchase_order(po, approval)
    second = await commit_purchase_order(po, approval)
    assert first.committed and second.committed
    assert first.confirmation == second.confirmation == "CONF-PO-2026-0042"
    assert clients["nordbolt"].calls == 2  # one quote and one unique commitment
    assert any(event.event_type == "commitment" for event in audit_log.events)


@pytest.mark.asyncio
async def test_commit_refuses_unscoped_approval() -> None:
    configure_demo_counterparties()
    po = PurchaseOrder(
        po_number="PO-1",
        supplier_id="nordbolt",
        quote_id="Q-1",
        quantity=2_000,
        unit_price=2.62,
        currency="GBP",
        delivery_date=date(2026, 9, 1),
    )
    approval = Approval(
        reference="APR-WRONG",
        approved_by="alex.buyer",
        po_number="PO-OTHER",
        maximum_amount=99_999,
    )
    result = await commit_purchase_order(po, approval)
    assert result.committed is False
    assert result.reason == "approval_does_not_authorize_order"


def test_wire_contract_excludes_negotiating_position() -> None:
    fields = set(BillOfMaterials.model_fields)
    assert fields == {"commodity", "requested_delivery_date", "line_items"}
    assert not fields.intersection({"budget", "target_price", "fallback_suppliers"})
