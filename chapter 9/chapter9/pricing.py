"""Usage normalization, versioned pricing, and invoice reconciliation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .models import ModelRates, NormalizedUsage, PriceCard, TurnCost

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRICE_CARD = ROOT / "data" / "pricing" / "illustrative_price_card_v1.json"


def load_price_card(path: Path = DEFAULT_PRICE_CARD) -> PriceCard:
    """Load the checked-in price card instead of trusting a mutable web page."""

    return PriceCard.model_validate_json(path.read_text(encoding="utf-8"))


def _value(source: object, *names: str, default: Any = 0) -> Any:
    for name in names:
        if isinstance(source, Mapping) and name in source:
            value = source[name]
        else:
            value = getattr(source, name, None)
        if value is not None:
            return value
    return default


def _details(source: object, *names: str) -> object:
    return _value(source, *names, default={}) or {}


def normalize_usage(usage: object) -> NormalizedUsage:
    """Map SDK/provider usage shapes onto the chapter's stable vocabulary.

    The adapter accepts flat teaching fixtures, OpenAI-style nested detail objects,
    dictionaries, or ordinary objects. Dashboards consume only the normalized form.
    """

    input_details = _details(
        usage,
        "input_tokens_details",
        "input_token_details",
        "input_details",
    )
    output_details = _details(
        usage,
        "output_tokens_details",
        "output_token_details",
        "output_details",
    )
    input_tokens = int(_value(usage, "input_tokens", "input", "prompt_tokens"))
    output_tokens = int(_value(usage, "output_tokens", "output", "completion_tokens"))
    cached = int(
        _value(
            usage,
            "cached_input_tokens",
            "cached_tokens",
            default=_value(input_details, "cached_tokens", "cached_input_tokens"),
        )
    )
    cache_write = int(
        _value(
            usage,
            "cache_write_tokens",
            "cache_creation_tokens",
            default=_value(
                input_details,
                "cache_write_tokens",
                "cache_creation_tokens",
            ),
        )
    )
    reasoning = int(
        _value(
            usage,
            "reasoning_tokens",
            default=_value(output_details, "reasoning_tokens"),
        )
    )
    return NormalizedUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        cache_write_tokens=cache_write,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning,
    )


def price_usage(usage: object, rates: ModelRates | Mapping[str, float]) -> TurnCost:
    """Price one normalized generation and retain actionable cost classes."""

    normalized = usage if isinstance(usage, NormalizedUsage) else normalize_usage(usage)
    parsed_rates = (
        rates if isinstance(rates, ModelRates) else ModelRates.model_validate(rates)
    )

    def per_million(tokens: int, rate: float) -> float:
        return tokens * rate / 1_000_000

    return TurnCost(
        uncached_input=per_million(
            normalized.uncached_input_tokens, parsed_rates.input
        ),
        cached_input=per_million(
            normalized.cached_input_tokens,
            parsed_rates.cached_input,
        ),
        cache_write=per_million(
            normalized.cache_write_tokens, parsed_rates.cache_write
        ),
        reasoning=per_million(normalized.reasoning_tokens, parsed_rates.output),
        visible_output=per_million(
            normalized.visible_output_tokens, parsed_rates.output
        ),
    )


def price_model_usage(usage: object, *, model: str, card: PriceCard) -> TurnCost:
    return price_usage(usage, card.rates_for(model))


def reconciliation_summary(
    estimated_usd: float,
    invoice_usd: float,
    *,
    tolerance: float = 0.05,
) -> dict[str, float | str | bool]:
    """Compare trace estimates with the invoice, which remains the truth."""

    if estimated_usd < 0 or invoice_usd < 0:
        raise ValueError("reconciliation amounts cannot be negative")
    denominator = invoice_usd or 1.0
    gap = invoice_usd - estimated_usd
    relative_gap = abs(gap) / denominator
    return {
        "estimated_usd": round(estimated_usd, 4),
        "invoice_usd": round(invoice_usd, 4),
        "gap_usd": round(gap, 4),
        "relative_gap": round(relative_gap, 4),
        "within_tolerance": relative_gap <= tolerance,
        "price_card_action": "review unmapped usage"
        if relative_gap > tolerance
        else "none",
    }


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
