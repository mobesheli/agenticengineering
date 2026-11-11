"""Failure drill: one supplier stops answering in the middle of a sourcing run.

    python -m drills.supplier_down

NordBolt goes offline. Three failed calls open its circuit breaker, the
fourth call is refused locally without touching the network, and the fan-out
still returns the other approved supplier's quote. No API key is needed.
"""

from __future__ import annotations

import asyncio

from chapter6.neighborhood import build_neighborhood
from chapter6.procurement import gather_quotes
from chapter6.registry import COUNTERPARTIES
from chapter6.remote import Delegation, request_supplier_quote
from chapter6.sample import BUYER, CASE, bracket_bom


async def main() -> None:
    hood = build_neighborhood()
    hood["nordbolt"].transport.online = False
    breaker = COUNTERPARTIES.require("nordbolt").breaker

    for attempt in range(1, 5):
        result = await request_supplier_quote(
            Delegation(hood.http, BUYER, CASE), "nordbolt", bracket_bom()
        )
        retry = f"retryable={result.retryable!s:<5}"
        print(
            f"call {attempt}: {result.error_class:<22} {retry} breaker={breaker.state}"
        )

    results = await gather_quotes(
        Delegation(hood.http, BUYER, CASE), bracket_bom(), "custom-brackets"
    )
    await hood.aclose()
    print()
    for result in results:
        answer = (
            f"{result.quote.unit_price:.2f} {result.quote.currency}"
            if result.ok
            else result.error_class
        )
        print(f"fan-out {result.supplier_id:<11}: {answer}")


if __name__ == "__main__":
    asyncio.run(main())
