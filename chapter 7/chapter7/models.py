"""The model registry. Model names appear in this file and nowhere else."""

from __future__ import annotations

from dataclasses import dataclass

from agents import ModelSettings
from openai.types.shared import Reasoning


@dataclass(frozen=True)
class ModelRegistry:
    reviewer: str = "gpt-6.1-terra"
    judge: str = "gpt-6.2-sol"


MODELS = ModelRegistry()
QUICK = ModelSettings(reasoning=Reasoning(effort="low"))

PRICES_AS_OF = "2026-11-20"
PRICE_PER_MILLION = {"reviewer": (1.00, 5.00), "judge": (2.00, 10.00)}


def cost_of(role: str, input_tokens: int, output_tokens: int) -> float:
    """Cost in US dollars of the tokens one role used."""
    input_price, output_price = PRICE_PER_MILLION[role]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
