"""Failure drill: the confirmation is lost, and the order is sent again.

    python -m drills.retry_same_message

The buyer approves a purchase order and the spine commits it. The spine then
commits the same order a second time, as it would after a timeout, and a
third time with the quantity changed. The supplier answers the repeat with
the confirmation it already issued and refuses the changed one. No API key
is needed.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from chapter6.contracts import Approval
from chapter6.neighborhood import build_neighborhood
from chapter6.procurement import commit_purchase_order, propose_order
from chapter6.remote import Delegation, request_supplier_quote
from chapter6.sample import BUYER, CASE, NEEDED_IN_DAYS, bracket_bom


async def main() -> None:
    hood = build_neighborhood()
    quoted = await request_supplier_quote(
        Delegation(hood.http, BUYER, CASE), "nordbolt", bracket_bom()
    )
    po = propose_order(
        "PO-88231",
        "nordbolt",
        quoted.quote,
        quantity=2000,
        due=date.today() + timedelta(days=NEEDED_IN_DAYS),
    )
    approval = Approval(
        reference="APR-5521",
        approved_by="a.okafor",
        po_number=po.po_number,
        maximum_amount=po.total_value,
        expires_on=quoted.quote.valid_until,
    )

    first = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE), po, approval
    )
    second = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE), po, approval
    )
    changed = po.model_copy(update={"quantity": 1500})
    third = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE), changed, approval
    )
    await hood.aclose()

    print(f"first commit   : {first.confirmation}")
    print(f"second commit  : {second.confirmation}")
    print(f"changed commit : committed={third.committed}")
    print(f"  {third.reason}")
    print(f"orders on the supplier's ledger: {len(hood['nordbolt'].ledger.orders)}")


if __name__ == "__main__":
    asyncio.run(main())
