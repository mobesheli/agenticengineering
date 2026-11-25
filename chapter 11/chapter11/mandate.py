"""A spending mandate: scoped, capped, expiring, and revocable."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mandate:
    agent: str
    signed_by: str
    instrument: str
    suppliers: tuple[str, ...]
    cap_per_order: float
    cap_per_day: float
    expires_day: int
    revoked: bool = False
    in_flight: list[dict] = field(default_factory=list)

    def spent_on(self, day: int) -> float:
        return sum(o["usd"] for o in self.in_flight if o["day"] == day)


def authorize(order: dict, mandate: Mandate) -> str | None:
    """Return the reason to refuse, or None after reserving the order."""
    if mandate.revoked:
        return "mandate revoked"
    if order["day"] > mandate.expires_day:
        return "mandate expired"
    if order["supplier"] not in mandate.suppliers:
        return "supplier is not on the mandate"
    if order["usd"] > mandate.cap_per_order:
        return f"${order['usd']:.0f} is over the order cap"
    if mandate.spent_on(order["day"]) + order["usd"] > mandate.cap_per_day:
        return "the day's cap would be exceeded"
    mandate.in_flight.append(order)
    return None


def revoke(mandate: Mandate) -> list[dict]:
    """Stop new orders. Return the ones already placed, which still need a
    decision from a person: cancel with the supplier, or let them complete."""
    mandate.revoked = True
    return list(mandate.in_flight)
