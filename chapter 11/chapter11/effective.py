"""What the provider actually ran, read from its own response, not from yours.

A release bundle records what you asked for. The response records what you got:
the model that answered and every setting that was applied, including the ones
you never set and the provider chose for you. The watch below collects that for
every run, so the model signal compares two observations and not one
observation with one intention.
"""

from __future__ import annotations

from typing import Any

from agents.tracing import Span, Trace, TracingProcessor
from agents.tracing.span_data import ResponseSpanData
from openai.types.responses import Response


def effective_configuration(response: Response) -> dict[str, Any]:
    reasoning, text = response.reasoning, response.text
    return {
        "model": response.model,
        "reasoning.effort": reasoning.effort if reasoning else None,
        "text.verbosity": text.verbosity if text else None,
        "service_tier": response.service_tier,
        "truncation": response.truncation,
        "temperature": response.temperature,
        "top_p": response.top_p,
        "parallel_tool_calls": response.parallel_tool_calls,
        "max_output_tokens": response.max_output_tokens,
    }


def differences(approved: dict, effective: dict) -> dict[str, tuple]:
    return {
        name: (approved.get(name), effective.get(name))
        for name in sorted(approved.keys() | effective.keys())
        if approved.get(name) != effective.get(name)
    }


class ConfigWatch(TracingProcessor):
    """Keeps the last effective configuration seen in each trace."""

    def __init__(self) -> None:
        self.seen: dict[str, dict[str, Any]] = {}

    def on_span_end(self, span: Span[Any]) -> None:
        data = span.span_data
        if isinstance(data, ResponseSpanData) and data.response is not None:
            self.seen[span.trace_id] = effective_configuration(data.response)

    def on_trace_start(self, trace: Trace) -> None: ...
    def on_trace_end(self, trace: Trace) -> None: ...
    def on_span_start(self, span: Span[Any]) -> None: ...
    def shutdown(self) -> None: ...
    def force_flush(self) -> None: ...
