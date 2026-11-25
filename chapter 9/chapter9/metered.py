"""The meter: reserve budget before a model call, and price the call after it.

It wraps any model the SDK can run, so one code path serves the scripted examples
and a live provider. The cost goes onto the trace as a span of its own.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from agents import Model, ModelResponse, custom_span
from openai.types.responses import ResponseCompletedEvent

from chapter9.budget import RunBudget
from chapter9.meter import TurnCost, price_usage
from chapter9.pricecard import PriceCard


def step_of(model_input: Any) -> str:
    """A call is planning until a tool result arrives, and reading after that."""
    last = (
        model_input[-1] if isinstance(model_input, list) and model_input else {}
    )
    kind = (
        last.get("type") if isinstance(last, dict) else getattr(last, "type", "")
    )
    return "read" if kind == "function_call_output" else "plan"


class MeteredModel(Model):
    def __init__(
        self,
        inner: Model,
        name: str,
        card: PriceCard,
        budget: RunBudget,
        step: str | None = None,
    ) -> None:
        self.inner, self.name, self.card = inner, name, card
        self.budget, self.step = budget, step

    async def get_response(
        self,
        system_instructions: str | None,
        input: Any,
        *args: Any,
        **more: Any,
    ) -> ModelResponse:
        rates = self.card.rates(self.name)
        hold = self.budget.estimate()
        self.budget.reserve(hold, "model")
        tag = {"model": self.name, "step": self.step or step_of(input)}
        with custom_span("model_call", tag) as span:
            try:
                response = await self.inner.get_response(
                    system_instructions, input, *args, **more
                )
            except BaseException:
                self.budget.settle(hold, 0.0)
                raise
            cost = price_usage(response.usage, rates)
            self.budget.settle(hold, cost.total)
            span.span_data.data.update(priced(response.usage, cost))
        return response

    async def stream_response(
        self,
        system_instructions: str | None,
        input: Any,
        *args: Any,
        **more: Any,
    ) -> AsyncIterator[Any]:
        rates = self.card.rates(self.name)
        hold = self.budget.estimate()
        self.budget.reserve(hold, "model")
        tag = {"model": self.name, "step": self.step or step_of(input)}
        spent = 0.0
        stream = self.inner.stream_response(
            system_instructions, input, *args, **more
        )
        with custom_span("model_call", tag) as span:
            try:
                async for event in stream:
                    done = isinstance(event, ResponseCompletedEvent)
                    if done and event.response.usage is not None:
                        cost = price_usage(event.response.usage, rates)
                        spent = cost.total
                        span.span_data.data.update(
                            priced(event.response.usage, cost)
                        )
                    yield event
            finally:
                self.budget.settle(hold, spent)


class StepRouter(Model):
    """Send each call to the model chosen for its step."""

    def __init__(self, routes: dict[str, Model]) -> None:
        self.routes = routes

    async def get_response(
        self,
        system_instructions: str | None,
        input: Any,
        *args: Any,
        **more: Any,
    ) -> ModelResponse:
        chosen = self.routes[step_of(input)]
        return await chosen.get_response(
            system_instructions, input, *args, **more
        )

    def stream_response(
        self,
        system_instructions: str | None,
        input: Any,
        *args: Any,
        **more: Any,
    ) -> AsyncIterator[Any]:
        chosen = self.routes[step_of(input)]
        return chosen.stream_response(system_instructions, input, *args, **more)


def priced(usage: Any, cost: TurnCost) -> dict[str, Any]:
    details = usage.input_tokens_details
    return {
        "input_tokens": usage.input_tokens,
        "cached_tokens": details.cached_tokens or 0,
        "cache_write_tokens": details.cache_write_tokens or 0,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.output_tokens_details.reasoning_tokens or 0,
        "cost": {name: round(usd, 6) for name, usd in asdict(cost).items()},
        "cost_usd": round(cost.total, 6),
    }
