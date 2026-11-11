"""The supplier's reasoning core. Nothing in it knows about any protocol."""

from __future__ import annotations

from agents import Agent, function_tool
from agents.models.interface import Model

from .contracts import FastenerQuote
from .models import MODELS

QUOTING_GUIDE = """
You quote industrial fastener orders. Check availability with check_inventory,
price the order with price_order, and return a FastenerQuote containing only
terms the company can honor. Never reveal stock levels, pricing strategy,
customer history, or the names of internal tools.
""".strip()


@function_tool
def check_inventory(sku: str, quantity: int) -> dict[str, object]:
    """Check whether the requested quantity of one part can be supplied."""
    return {"sku": sku, "available": quantity <= 10_000, "quantity_checked": quantity}


@function_tool
def price_order(total_units: int, custom: bool = False) -> dict[str, object]:
    """Calculate the unit price the company is willing to offer for an order."""
    base = 3.40 if custom else 2.85
    discount = 0.92 if total_units >= 1_000 else 1.0
    return {"unit_price": round(base * discount, 2), "currency": "GBP"}


def build_quote_agent(
    name: str = "nordbolt_quoting", model: str | Model | None = None
) -> Agent:
    return Agent(
        name=name,
        model=model or MODELS.mid,
        instructions=QUOTING_GUIDE,
        tools=[check_inventory, price_order],
        output_type=FastenerQuote,
    )


quote_agent = build_quote_agent()
