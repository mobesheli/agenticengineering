"""The NordBolt reasoning core that sits behind the A2A protocol surface."""

from __future__ import annotations

from agents import Agent, function_tool

from .contracts import FastenerQuote
from .models import MODELS

QUOTING_GUIDE = """
You quote industrial fastener orders for NordBolt. Use the inventory and pricing
tools, return only terms NordBolt can honor, and produce a FastenerQuote. Never
reveal inventory levels, pricing strategy, customer history, or internal tools.
""".strip()


@function_tool
def check_inventory(sku: str, quantity: int) -> dict[str, object]:
    """Check whether NordBolt can supply a requested fastener quantity."""

    return {"sku": sku, "available": quantity <= 10_000, "quantity_checked": quantity}


@function_tool
def price_order(total_units: int, custom: bool = False) -> dict[str, object]:
    """Calculate an internal unit-price proposal for a fastener order."""

    base = 3.40 if custom else 2.85
    discount = 0.92 if total_units >= 1_000 else 1.0
    return {"unit_price": round(base * discount, 2), "currency": "GBP"}


def build_quote_agent() -> Agent:
    """Build the unchanged OpenAI Agents SDK agent described in the chapter."""

    return Agent(
        name="nordbolt_quoting",
        model=MODELS.mid,
        instructions=QUOTING_GUIDE,
        tools=[check_inventory, price_order],
        output_type=FastenerQuote,
    )


quote_agent = build_quote_agent()
