"""Call a NordBolt server running in another terminal, with a real model behind it.

    python -m chapter6.server          # terminal one, needs OPENAI_API_KEY
    python -m examples.live_quote      # terminal two

This is the same client path the drills use. The only differences are that
the card is fetched over a real socket and the quote is written by a model.
"""

from __future__ import annotations

import asyncio

import httpx

from chapter6.card import build_card, sign_card
from chapter6.neighborhood import NORDBOLT, approve
from chapter6.registry import CounterpartyRegistry
from chapter6.remote import Delegation, request_supplier_quote
from chapter6.sample import BUYER, CASE, bracket_bom

LOCAL_URL = "http://127.0.0.1:9999"


async def main() -> None:
    card = sign_card(build_card(base_url=LOCAL_URL), kid=NORDBOLT.kid)
    entry = approve(NORDBOLT, card, agent_url=LOCAL_URL)
    entry.sla_seconds = 60.0
    registry = CounterpartyRegistry()
    registry.onboard(entry)

    async with httpx.AsyncClient() as http:
        result = await request_supplier_quote(
            Delegation(http, BUYER, CASE, registry), "nordbolt", bracket_bom()
        )
    if result.ok:
        quote = result.quote
        price = f"{quote.unit_price:.2f} {quote.currency}"
        print(f"quote {quote.quote_id}: {price}, {quote.lead_time_days} days")
    else:
        print(f"no quote: {result.error_class} ({result.detail})")


if __name__ == "__main__":
    asyncio.run(main())
