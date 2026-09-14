"""Thin adapters for the pinned OpenAI Agents SDK tracing interfaces."""

from __future__ import annotations

from typing import Any

from agents.tracing import GenerationSpanData, TracingProcessor

from .models import PriceCard
from .pricing import normalize_usage, price_model_usage

IDENTITY_KEYS = (
    "tenant",
    "plant",
    "principal",
    "agent_version",
    "prompt_bundle",
    "tool_catalog_version",
)


class PricingProcessor(TracingProcessor):
    """Attach stable usage, price-card version, and run identity to generation spans.

    The SDK requires trace processors not to disrupt a run. Unknown models are
    therefore recorded as enrichment errors here; the pre-call budget still fails
    closed before a metered request.
    """

    def __init__(
        self, price_card: PriceCard, downstream: TracingProcessor | None = None
    ) -> None:
        self.price_card = price_card
        self.downstream = downstream
        self.identity: dict[str, dict[str, Any]] = {}
        self.enrichment_errors: list[dict[str, str]] = []

    def on_trace_start(self, trace: Any) -> None:
        exported = trace.export() or {}
        metadata = exported.get("metadata") or getattr(trace, "metadata", None) or {}
        self.identity[trace.trace_id] = {
            key: metadata.get(key)
            for key in IDENTITY_KEYS
            if metadata.get(key) is not None
        }
        if self.downstream:
            self.downstream.on_trace_start(trace)

    def on_trace_end(self, trace: Any) -> None:
        if self.downstream:
            self.downstream.on_trace_end(trace)
        self.identity.pop(trace.trace_id, None)

    def on_span_start(self, span: Any) -> None:
        if self.downstream:
            self.downstream.on_span_start(span)

    def on_span_end(self, span: Any) -> None:
        data = span.span_data
        if isinstance(data, GenerationSpanData) and data.usage and data.model:
            try:
                normalized = normalize_usage(data.usage)
                cost = price_model_usage(
                    normalized, model=data.model, card=self.price_card
                )
                data.usage = {
                    **data.usage,
                    "chapter9": {
                        "normalized": normalized.model_dump(),
                        "cost": cost.model_dump(),
                        "cost_usd": round(cost.total, 8),
                        "price_card_version": self.price_card.version,
                        **self.identity.get(span.trace_id, {}),
                    },
                }
            except (KeyError, TypeError, ValueError) as exc:
                self.enrichment_errors.append(
                    {
                        "trace_id": span.trace_id,
                        "span_id": span.span_id,
                        "error": str(exc),
                    }
                )
        if self.downstream:
            self.downstream.on_span_end(span)

    def shutdown(self) -> None:
        if self.downstream:
            self.downstream.shutdown()

    def force_flush(self) -> None:
        if self.downstream:
            self.downstream.force_flush()
