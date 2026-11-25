"""The price card: one versioned file that every cost figure is computed from."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from chapter9.settings import DATA


class UnknownPrice(LookupError):
    """A model or tool that is not on the card. It is an error, never free."""


@dataclass(frozen=True)
class Rates:
    input: float
    cached_input: float
    cache_write: float
    output: float


@dataclass(frozen=True)
class PriceCard:
    version: str
    models: dict[str, Rates]
    tools: dict[str, float]
    overheads: dict[str, float]
    review_usd_per_minute: float

    def rates(self, model: str) -> Rates:
        if model not in self.models:
            raise UnknownPrice(
                f"model {model!r} is not on price card {self.version}"
            )
        return self.models[model]

    def tool_fee(self, tool: str) -> float:
        if tool not in self.tools:
            raise UnknownPrice(
                f"tool {tool!r} is not on price card {self.version}"
            )
        return self.tools[tool]


def load_price_card(path: Path = DATA / "price-card.yaml") -> PriceCard:
    raw = yaml.safe_load(path.read_text())
    return PriceCard(
        version=str(raw["version"]),
        models={name: Rates(**rates) for name, rates in raw["models"].items()},
        tools=dict(raw["tools"]),
        overheads={name: item["usd"] for name, item in raw["overheads"].items()},
        review_usd_per_minute=raw["review"]["planner_usd_per_minute"],
    )
