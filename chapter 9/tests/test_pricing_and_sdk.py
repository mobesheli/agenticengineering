from __future__ import annotations

import pytest
from agents.tracing import GenerationSpanData
from agents.usage import Usage

from chapter9.pricing import load_price_card, normalize_usage, price_model_usage
from chapter9.sdk import PricingProcessor


def test_usage_adapter_normalizes_nested_sdk_fields() -> None:
    usage = {
        "input_tokens": 10_000,
        "input_tokens_details": {"cached_tokens": 6_000, "cache_write_tokens": 1_000},
        "output_tokens": 2_000,
        "output_tokens_details": {"reasoning_tokens": 1_200},
    }
    normalized = normalize_usage(usage)
    assert normalized.uncached_input_tokens == 3_000
    assert normalized.cached_input_tokens == 6_000
    assert normalized.cache_write_tokens == 1_000
    assert normalized.reasoning_tokens == 1_200
    assert normalized.visible_output_tokens == 800


def test_usage_adapter_reads_the_pinned_sdk_usage_object() -> None:
    usage = Usage(
        input_tokens=100,
        input_tokens_details={"cached_tokens": 50, "cache_write_tokens": 10},
        output_tokens=20,
        output_tokens_details={"reasoning_tokens": 12},
        total_tokens=120,
    )
    assert normalize_usage(usage).model_dump() == {
        "input_tokens": 100,
        "cached_input_tokens": 50,
        "cache_write_tokens": 10,
        "output_tokens": 20,
        "reasoning_tokens": 12,
    }


def test_price_usage_separates_the_five_actionable_cost_classes() -> None:
    card = load_price_card()
    usage = {
        "input_tokens": 10_000,
        "cached_tokens": 6_000,
        "cache_write_tokens": 1_000,
        "output_tokens": 2_000,
        "reasoning_tokens": 1_200,
    }
    cost = price_model_usage(usage, model="maintenance-mid", card=card)
    assert cost.uncached_input == pytest.approx(0.009)
    assert cost.cached_input == pytest.approx(0.0018)
    assert cost.cache_write == pytest.approx(0.00375)
    assert cost.reasoning == pytest.approx(0.0144)
    assert cost.visible_output == pytest.approx(0.0096)
    assert cost.total == pytest.approx(0.03855)


def test_unknown_model_fails_closed() -> None:
    with pytest.raises(KeyError, match="unknown models fail closed"):
        load_price_card().rates_for("brand-new-unpriced-model")


class FakeTrace:
    trace_id = "trace-sdk"

    def export(self):
        return {
            "metadata": {
                "tenant": "manufacturer",
                "plant": "Plant A",
                "principal": "planner-42",
                "agent_version": "9.0.0",
                "prompt_bundle": "bundle-v1",
                "tool_catalog_version": "catalog-v2",
            }
        }


class FakeSpan:
    trace_id = "trace-sdk"
    span_id = "span-sdk"

    def __init__(self):
        self.span_data = GenerationSpanData(
            model="maintenance-mid",
            usage={"input_tokens": 1_000, "output_tokens": 100},
        )


def test_sdk_pricing_processor_enriches_usage_without_a_live_call() -> None:
    processor = PricingProcessor(load_price_card())
    processor.on_trace_start(FakeTrace())
    span = FakeSpan()
    processor.on_span_end(span)
    chapter = span.span_data.usage["chapter9"]
    assert chapter["plant"] == "Plant A"
    assert chapter["price_card_version"] == load_price_card().version
    assert chapter["cost_usd"] > 0
    processor.on_trace_end(FakeTrace())
    assert processor.enrichment_errors == []
