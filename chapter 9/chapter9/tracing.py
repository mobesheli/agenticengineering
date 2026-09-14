"""Immutable-at-export trace records with identity, price, and outcome joins."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models import SpanRecord, TraceIdentity, TraceRecord
from .pricing import canonical_json


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def arguments_hash(arguments: object) -> str:
    return hashlib.sha256(canonical_json(arguments).encode()).hexdigest()


class InMemoryLedger:
    """Teaching ledger whose public reads return validated copies.

    Production deployments replace this with an append-only telemetry store under
    an identity the agent cannot read or mutate.
    """

    def __init__(self) -> None:
        self._traces: dict[str, TraceRecord] = {}
        self._lock = threading.RLock()

    def start_trace(
        self,
        *,
        identity: TraceIdentity,
        severity: str,
        period: str,
        baseline_usd: float,
        trace_id: str | None = None,
        started_at: datetime | None = None,
    ) -> TraceRecord:
        record = TraceRecord(
            trace_id=trace_id or f"trace-{uuid4().hex[:16]}",
            identity=identity,
            started_at=started_at or utc_now(),
            severity=severity,
            period=period,
            baseline_usd=baseline_usd,
        )
        with self._lock:
            if record.trace_id in self._traces:
                raise ValueError(f"trace {record.trace_id} already exists")
            self._traces[record.trace_id] = record
        return record.model_copy(deep=True)

    def append_span(self, trace_id: str, span: SpanRecord) -> None:
        if span.trace_id != trace_id:
            raise ValueError("span trace identifier does not match its parent trace")
        with self._lock:
            trace = self._traces[trace_id]
            if any(existing.span_id == span.span_id for existing in trace.spans):
                raise ValueError(f"span {span.span_id} already exists")
            trace.spans.append(span.model_copy(deep=True))

    def label_outcome(
        self,
        trace_id: str,
        *,
        outcome: str,
        outcome_ref: str | None,
        review_minutes: float,
        review_rate_per_minute: float,
        stop_reason: str | None = None,
    ) -> None:
        with self._lock:
            trace = self._traces[trace_id]
            updated = trace.model_copy(
                update={
                    "outcome": outcome,
                    "outcome_ref": outcome_ref,
                    "review_minutes": review_minutes,
                    "review_rate_per_minute": review_rate_per_minute,
                    "stop_reason": stop_reason,
                }
            )
            self._traces[trace_id] = TraceRecord.model_validate(updated.model_dump())

    def get(self, trace_id: str) -> TraceRecord:
        with self._lock:
            return self._traces[trace_id].model_copy(deep=True)

    def traces(self) -> list[TraceRecord]:
        with self._lock:
            return [record.model_copy(deep=True) for record in self._traces.values()]

    def extend(self, traces: Iterable[TraceRecord]) -> None:
        with self._lock:
            for trace in traces:
                if trace.trace_id in self._traces:
                    raise ValueError(f"trace {trace.trace_id} already exists")
                self._traces[trace.trace_id] = trace.model_copy(deep=True)

    def priced_rows(self) -> list[dict[str, Any]]:
        rows = []
        for trace in self.traces():
            rows.append(
                {
                    "trace_id": trace.trace_id,
                    "period": trace.period,
                    "plant": trace.identity.plant,
                    "severity": trace.severity,
                    "outcome": trace.outcome,
                    "outcome_ref": trace.outcome_ref,
                    "machine_cost_usd": trace.machine_cost_usd,
                    "review_minutes": trace.review_minutes,
                    "review_rate_per_minute": trace.review_rate_per_minute,
                    "cost_usd": trace.fully_loaded_cost_usd,
                    "baseline_usd": trace.baseline_usd,
                    "stop_reason": trace.stop_reason,
                }
            )
        return rows


def new_span(
    *,
    trace_id: str,
    kind: str,
    name: str,
    started_at: datetime,
    duration_ms: float,
    parent_id: str | None = None,
    step_type: str | None = None,
    model: str | None = None,
    tool_name: str | None = None,
    arguments: object | None = None,
    status: str = "ok",
    usage: object | None = None,
    cost: object | None = None,
    direct_cost_usd: float = 0.0,
    attributes: dict[str, Any] | None = None,
) -> SpanRecord:
    return SpanRecord(
        span_id=f"span-{uuid4().hex[:16]}",
        trace_id=trace_id,
        parent_id=parent_id,
        kind=kind,  # type: ignore[arg-type]
        name=name,
        step_type=step_type,
        model=model,
        tool_name=tool_name,
        arguments_hash=arguments_hash(arguments) if arguments is not None else None,
        status=status,  # type: ignore[arg-type]
        started_at=started_at,
        duration_ms=duration_ms,
        usage=usage,
        cost=cost,
        direct_cost_usd=direct_cost_usd,
        attributes=attributes or {},
    )
