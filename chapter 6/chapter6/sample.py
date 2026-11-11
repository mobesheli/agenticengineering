"""The sourcing requirement used throughout the chapter's examples."""

from __future__ import annotations

from datetime import date, timedelta

BUYER = "buyer/a.okafor"
CASE = "SR-2291"
NEEDED_IN_DAYS = 42


def bracket_bom(
    drawing_rev: str | None = "C",
    description: str = "Custom steel bracket, zinc plated",
) -> dict:
    """Two thousand custom brackets, needed in six weeks."""
    return {
        "commodity": "custom-brackets",
        "requested_delivery_date": (
            date.today() + timedelta(days=NEEDED_IN_DAYS)
        ).isoformat(),
        "line_items": [
            {
                "sku": "CB-42",
                "description": description,
                "quantity": 2000,
                "custom": True,
                "drawing_rev": drawing_rev,
            }
        ],
    }
