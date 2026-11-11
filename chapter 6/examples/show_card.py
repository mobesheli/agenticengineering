"""Build NordBolt's Agent Card, sign it, and verify it the way a caller would.

python -m examples.show_card
"""

from __future__ import annotations

import json

from a2a.types import AgentCard
from a2a.utils.signing import SignatureVerificationError

from chapter6.card import build_card, card_fingerprint, card_to_json, sign_card
from chapter6.neighborhood import NORDBOLT, approve


def main() -> None:
    card = sign_card(build_card(), kid="nordbolt-2026-01")
    shown = card_to_json(card)
    shown["skills"] = shown["skills"][:1]
    for signature in shown["signatures"]:
        signature["protected"] = signature["protected"][:24] + "..."
        signature["signature"] = signature["signature"][:16] + "..."
    print(json.dumps(shown, indent=2))

    trust = approve(NORDBOLT, card).trust
    verify = trust.verifier()
    verify(card)
    print("\nsignature : valid under key nordbolt-2026-01")
    print(f"fingerprint: {card_fingerprint(card)[:12]}")

    tampered = AgentCard()
    tampered.CopyFrom(card)
    tampered.skills[0].description = "Also approves purchase orders."
    try:
        verify(tampered)
    except SignatureVerificationError as refused:
        print(f"tampered  : refused ({type(refused).__name__})")


if __name__ == "__main__":
    main()
