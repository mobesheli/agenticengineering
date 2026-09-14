"""Export deterministic trace records to the local one-container OTLP stack."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from opentelemetry import trace as otel_trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from .models import TraceRecord


def _attributes(
    trace: TraceRecord,
    extra: dict[str, Any] | None = None,
    *,
    include_trace_totals: bool = True,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "chapter9.trace_id": trace.trace_id,
        "chapter9.tenant": trace.identity.tenant,
        "chapter9.plant": trace.identity.plant,
        "chapter9.principal": trace.identity.principal,
        "chapter9.workflow": trace.identity.workflow,
        "chapter9.severity": trace.severity,
        "chapter9.period": trace.period,
        "chapter9.outcome": trace.outcome or "unlabeled",
        "chapter9.baseline_usd": trace.baseline_usd,
    }
    if include_trace_totals:
        values["chapter9.cost_usd"] = trace.fully_loaded_cost_usd
    for key, value in (extra or {}).items():
        if isinstance(value, (str, bool, int, float)):
            values[f"chapter9.{key}"] = value
    return values


def export_traces_to_otlp(
    traces: Sequence[TraceRecord],
    *,
    endpoint: str = "http://localhost:4318/v1/traces",
) -> int:
    """Send traces over OTLP/HTTP. The caller deliberately opts into network I/O."""

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "chapter9-maintenance",
                "service.version": "9.0.0",
                "deployment.environment.name": "local-demo",
            }
        )
    )
    provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    tracer = provider.get_tracer("agenticengineering.chapter9")
    sent = 0
    for trace in traces:
        recorded_root = next(
            (span for span in trace.spans if span.kind == "agent"), None
        )
        root_started_at = (
            recorded_root.started_at if recorded_root else trace.started_at
        )
        root = tracer.start_span(
            recorded_root.name if recorded_root else "agent.maintenance_planning",
            start_time=int(root_started_at.timestamp() * 1_000_000_000),
            attributes=_attributes(trace),
        )
        root_context = otel_trace.set_span_in_context(root)
        latest_end = root_started_at
        for span in trace.spans:
            if recorded_root and span.span_id == recorded_root.span_id:
                continue
            start_ns = int(span.started_at.timestamp() * 1_000_000_000)
            end_ns = start_ns + int(span.duration_ms * 1_000_000)
            child = tracer.start_span(
                span.name,
                context=root_context,
                start_time=start_ns,
                attributes=_attributes(
                    trace,
                    {
                        "span_kind": span.kind,
                        "step_type": span.step_type or "",
                        "model": span.model or "",
                        "tool_name": span.tool_name or "",
                        "status": span.status,
                        "span_cost_usd": span.cost_usd,
                    },
                    include_trace_totals=False,
                ),
            )
            child.end(end_time=end_ns)
            sent += 1
            candidate = span.started_at + timedelta(milliseconds=span.duration_ms)
            latest_end = max(latest_end, candidate)
        root.end(end_time=int(latest_end.timestamp() * 1_000_000_000))
        sent += 1
    provider.force_flush()
    provider.shutdown()
    return sent
