"""The capstone: one sourcing run across three organizations.

    python -m drills.sourcing_run

The spine fans a bill of materials out to two approved suppliers, compares
the quotes in plain code, puts a purchase order proposal in front of a named
buyer, commits the approved order, and prints the boundary audit trail. No
API key is needed.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from chapter6.audit import audit_log
from chapter6.contracts import Approval
from chapter6.neighborhood import build_neighborhood
from chapter6.procurement import (
    commit_purchase_order,
    compare_quotes,
    gather_quotes,
    propose_order,
)
from chapter6.remote import Delegation
from chapter6.sample import BUYER, CASE, NEEDED_IN_DAYS, bracket_bom


async def main() -> None:
    hood = build_neighborhood()
    audit_log.clear()

    results = await gather_quotes(
        Delegation(hood.http, "procurement-spine", CASE),
        bracket_bom(),
        "custom-brackets",
    )
    print("quotes")
    for r in results:
        q = r.quote
        price = f"{q.unit_price:.2f} {q.currency}"
        print(f"  {r.supplier_id:<11} {price}  {q.lead_time_days} days  {q.quote_id}")

    winner = compare_quotes(results, needed_in_days=NEEDED_IN_DAYS)
    po = propose_order(
        "PO-88231",
        winner.supplier_id,
        winner.quote,
        quantity=2000,
        due=date.today() + timedelta(days=NEEDED_IN_DAYS),
    )
    total = f"{po.quantity} x {po.unit_price:.2f} = {po.total_value:,.2f} {po.currency}"
    print(f"\nproposal   {po.po_number} to {po.supplier_id}: {total}")

    approval = Approval(
        reference="APR-5521",
        approved_by="a.okafor",
        po_number=po.po_number,
        maximum_amount=po.total_value,
        expires_on=winner.quote.valid_until,
    )
    limit = f"up to {approval.maximum_amount:,.2f}, until {approval.expires_on}"
    print(f"approval   {approval.reference} by {approval.approved_by}, {limit}")

    commit = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE), po, approval
    )
    await hood.aclose()
    print(f"commit     committed={commit.committed} confirmation={commit.confirmation}")

    print("\nboundary audit trail")
    for e in audit_log.events:
        state = e.state or "-"
        print(f"  {e.event:<14} {e.counterparty_id:<11} {state:<10} {e.authorized_by}")


if __name__ == "__main__":
    asyncio.run(main())
