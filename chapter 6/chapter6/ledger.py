"""The supplier's own records: issued quotes, accepted orders, and replays.

This stands in for the supplier's database. It is what lets the supplier keep
its side of the idempotency contract: the same message twice returns the same
result, and the same message identifier with different content is refused.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .contracts import BillOfMaterials, FastenerQuote, OrderConfirmation


def content_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class ReplayConflict(ValueError):
    """A message identifier was reused with different content."""


@dataclass
class SupplierLedger:
    quotes: dict[str, FastenerQuote] = field(default_factory=dict)
    orders: dict[str, OrderConfirmation] = field(default_factory=dict)
    parked: dict[str, BillOfMaterials] = field(default_factory=dict)
    _seen: dict[str, tuple[str, dict[str, Any]]] = field(default_factory=dict)

    def replay(self, message_id: str, payload: Any) -> dict[str, Any] | None:
        """Return the stored result for a repeated message, if there is one."""
        seen = self._seen.get(message_id)
        if seen is None:
            return None
        stored_hash, result = seen
        if stored_hash != content_hash(payload):
            raise ReplayConflict("message ID reused with different content")
        return result

    def remember(self, message_id: str, payload: Any, result: dict[str, Any]) -> None:
        self._seen[message_id] = (content_hash(payload), result)

    def accept_order(self, order: dict[str, Any], today: date) -> OrderConfirmation:
        quote = self.quotes.get(order.get("quote_id", ""))
        if quote is None:
            raise ValueError("order references a quote this agent did not issue")
        if today > quote.valid_until:
            raise ValueError("the quote has expired")
        if abs(float(order["unit_price"]) - quote.unit_price) > 0.005:
            raise ValueError("order price does not match the quoted price")
        confirmation = OrderConfirmation(
            confirmation=f"CONF-{order['po_number']}",
            po_number=order["po_number"],
            quote_id=quote.quote_id,
            accepted=True,
        )
        self.orders[confirmation.po_number] = confirmation
        return confirmation
