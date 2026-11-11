"""Ask an approved supplier agent for a quote, over A2A, and read what came back.

python -m examples.quote_roundtrip
"""

from __future__ import annotations

import asyncio

from chapter6.audit import audit_log
from chapter6.neighborhood import build_neighborhood
from chapter6.remote import Delegation, request_supplier_quote
from chapter6.sample import BUYER, CASE, bracket_bom


async def main() -> None:
    hood = build_neighborhood()
    audit_log.clear()
    result = await request_supplier_quote(
        Delegation(hood.http, BUYER, CASE), "nordbolt", bracket_bom()
    )
    await hood.aclose()

    quote = result.quote
    print(f"ok          : {result.ok}")
    print(f"quote       : {quote.quote_id}")
    print(f"unit price  : {quote.unit_price:.2f} {quote.currency}")
    print(f"lead time   : {quote.lead_time_days} days")
    print(f"valid until : {quote.valid_until}")
    event = audit_log.events[-1]
    print(
        f"\naudit       : {event.event} with {event.counterparty_id}, card {event.card_version}"
    )
    print(
        f"              task state {event.state}, authorized by {event.authorized_by}"
    )
    print(f"              request {event.request_hash}, response {event.response_hash}")


if __name__ == "__main__":
    asyncio.run(main())
