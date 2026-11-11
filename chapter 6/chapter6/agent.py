"""The supplier's reasoning core. Nothing in it knows about any protocol."""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from agents import Agent, function_tool
from agents.models.interface import Model

from .contracts import FastenerQuote
from .models import MODELS

QUOTING_GUIDE = """
You quote industrial fastener orders. Check availability with check_inventory,
then call price_order once for the whole order. Return a FastenerQuote whose
quote_id, unit_price, currency, lead_time_days, and valid_until are copied
exactly from the price_order result. Never estimate, adjust, or invent any of
those five values. Use conditions only for terms the company can honor. Never
reveal stock levels, pricing strategy, customer history, or the names of
internal tools.
""".strip()

QUOTE_VALID_DAYS = 14


@function_tool
def check_inventory(sku: str, quantity: int) -> dict[str, object]:
    """Check whether the requested quantity of one part can be supplied."""
    return {"sku": sku, "available": quantity <= 10_000, "quantity_checked": quantity}


def quote_terms(total_units: int, custom: bool) -> dict[str, object]:
    """Every commercial term of a quote. The model copies these and invents none."""
    base = 3.40 if custom else 2.85
    discount = 0.92 if total_units >= 1_000 else 1.0
    today = date.today()
    request = f"{total_units}:{custom}:{today.isoformat()}"
    reference = hashlib.sha256(request.encode()).hexdigest()[:6].upper()
    return {
        "quote_id": f"NB-{reference}",
        "unit_price": round(base * discount, 2),
        "currency": "GBP",
        "lead_time_days": 28 if custom else 14,
        "valid_until": (today + timedelta(days=QUOTE_VALID_DAYS)).isoformat(),
    }


@function_tool
def price_order(total_units: int, custom: bool = False) -> dict[str, object]:
    """Price an order and issue the terms the company is willing to offer."""
    return quote_terms(total_units, custom)


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
