"""Failure drill: the supplier needs something before it can continue.

    python -m drills.parked_task

The bill of materials leaves out the drawing revision for a custom part. The
supplier's agent parks the task in the input-required state and asks. The
sourcing spine answers on the same task, and the quote completes. No API key
is needed.
"""

from __future__ import annotations

import asyncio

from chapter6.neighborhood import build_neighborhood
from chapter6.remote import Delegation, answer_supplier_question, request_supplier_quote
from chapter6.sample import BUYER, CASE, bracket_bom


async def main() -> None:
    hood = build_neighborhood()
    parked = await request_supplier_quote(
        Delegation(hood.http, BUYER, CASE), "nordbolt", bracket_bom(drawing_rev=None)
    )
    print(f"first answer : {parked.error_class}")
    print(f"question     : {parked.detail}")
    print(f"model calls  : {len(hood['nordbolt'].model.calls)}")

    resumed = await answer_supplier_question(
        Delegation(hood.http, BUYER, CASE),
        "nordbolt",
        parked.task_id,
        {"drawing_rev": "C"},
    )
    await hood.aclose()
    print(f"\nsame task    : {resumed.task_id == parked.task_id}")
    quote = resumed.quote
    print(
        f"second answer: quote {quote.quote_id}, {quote.unit_price:.2f} {quote.currency}"
    )
    print(f"model calls  : {len(hood['nordbolt'].model.calls)}")


if __name__ == "__main__":
    asyncio.run(main())
