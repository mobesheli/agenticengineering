"""Failure drill: three cards, and only one of them is the card we approved.

    python -m drills.untrusted_card

The registry holds NordBolt's current and previous signing keys and the
fingerprint of the card that was approved. The drill serves three cards in
turn: the approved card re-signed with the previous key during a rotation,
the approved card signed by somebody else, and a changed card with a valid
signature. No API key is needed.
"""

from __future__ import annotations

import asyncio

from a2a.types import AgentCard

from chapter6.card import build_card, sign_card
from chapter6.neighborhood import NORDBOLT, Neighborhood, build_neighborhood
from chapter6.remote import Delegation, request_supplier_quote
from chapter6.sample import BUYER, CASE, bracket_bom


async def attempt(hood: Neighborhood, label: str) -> None:
    result = await request_supplier_quote(
        Delegation(hood.http, BUYER, CASE), "nordbolt", bracket_bom()
    )
    outcome = "quote received" if result.ok else result.error_class
    print(f"{label:<24}: {outcome}")
    if result.detail:
        print(f"{'':<24}  {result.detail}")


async def main() -> None:
    hood = build_neighborhood()
    approved = build_card(
        name="nordbolt-quoting-agent",
        organization=NORDBOLT.organization,
        base_url=NORDBOLT.base_url,
    )

    hood.serve("nordbolt", sign_card(_copy(approved), kid="nordbolt-2025-01"))
    await attempt(hood, "previous key, in date")

    hood.serve("nordbolt", sign_card(_copy(approved), kid="impostor"))
    await attempt(hood, "unknown key")

    changed = _copy(approved)
    changed.version = "1.5.0"
    changed.skills[0].description += " Now also negotiates payment terms."
    hood.serve("nordbolt", sign_card(changed, kid="nordbolt-2026-01"))
    await attempt(hood, "valid key, changed card")
    await hood.aclose()


def _copy(card: AgentCard) -> AgentCard:
    clone = AgentCard()
    clone.CopyFrom(card)
    return clone


if __name__ == "__main__":
    asyncio.run(main())
