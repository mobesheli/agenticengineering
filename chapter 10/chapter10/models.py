"""Model settings. The model names live in the release bundle and nowhere in code."""

from __future__ import annotations

from agents import ModelSettings
from openai.types.shared import Reasoning

from chapter10.bundle import Bundle

PRICES_AS_OF = "2026-11-20"
PRICE_PER_MILLION = {"primary": (1.00, 5.00), "fallback": (0.10, 0.50)}


def model_for(bundle: Bundle, role: str = "primary") -> tuple[str, ModelSettings]:
    """The pinned model and its settings for one role in the bundle."""
    pin = bundle.model[role]
    return pin.id, ModelSettings(reasoning=Reasoning(effort=pin.effort))


def cost_of(role: str, input_tokens: int, output_tokens: int) -> float:
    """Cost in US dollars of the tokens one role used."""
    input_price, output_price = PRICE_PER_MILLION[role]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
