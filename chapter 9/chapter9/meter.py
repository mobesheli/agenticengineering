"""Turn one model call's usage report into the cost lines a team can act on."""

from __future__ import annotations

from dataclasses import astuple, dataclass

from agents.usage import Usage

from chapter9.pricecard import Rates

MILLION = 1_000_000


@dataclass(frozen=True)
class TurnCost:
    uncached_input: float
    cached_input: float
    cache_write: float
    reasoning: float
    visible_output: float

    @property
    def total(self) -> float:
        return sum(astuple(self))


def price_usage(usage: Usage, rates: Rates) -> TurnCost:
    cached = usage.input_tokens_details.cached_tokens or 0
    written = usage.input_tokens_details.cache_write_tokens or 0
    reasoning = usage.output_tokens_details.reasoning_tokens or 0
    uncached = usage.input_tokens - cached - written
    visible = usage.output_tokens - reasoning
    return TurnCost(
        uncached_input=uncached * rates.input / MILLION,
        cached_input=cached * rates.cached_input / MILLION,
        cache_write=written * rates.cache_write / MILLION,
        reasoning=reasoning * rates.output / MILLION,
        visible_output=visible * rates.output / MILLION,
    )


def usage_of(
    input_tokens: int,
    output_tokens: int,
    cached: int = 0,
    written: int = 0,
    reasoning: int = 0,
) -> Usage:
    """Build a usage report in the SDK's own shape, for fixtures and tests."""
    from openai.types.responses.response_usage import (
        InputTokensDetails,
        OutputTokensDetails,
    )

    return Usage(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=InputTokensDetails(
            cached_tokens=cached, cache_write_tokens=written
        ),
        output_tokens_details=OutputTokensDetails(reasoning_tokens=reasoning),
    )
