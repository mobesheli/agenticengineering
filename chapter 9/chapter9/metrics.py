"""Production metrics that pair behavior, cost, quality, and uncertainty."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

from .models import PlantValueRow, TraceRecord


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def wilson_interval(
    successes: int, attempts: int, z: float = 1.96
) -> tuple[float, float]:
    """A bounded binomial interval that behaves sensibly on small dashboard cells."""

    if attempts < 0 or successes < 0 or successes > attempts:
        raise ValueError("success counts must satisfy 0 <= successes <= attempts")
    if attempts == 0:
        return 0.0, 0.0
    proportion = successes / attempts
    denominator = 1 + z**2 / attempts
    center = (proportion + z**2 / (2 * attempts)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / attempts + z**2 / (4 * attempts**2))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _row(trace_or_row: TraceRecord | dict[str, Any]) -> dict[str, Any]:
    if isinstance(trace_or_row, TraceRecord):
        return {
            "plant": trace_or_row.identity.plant,
            "severity": trace_or_row.severity,
            "outcome": trace_or_row.outcome,
            "cost_usd": trace_or_row.fully_loaded_cost_usd,
            "baseline_usd": trace_or_row.baseline_usd,
        }
    machine = float(trace_or_row.get("machine_cost_usd", 0.0))
    review = float(trace_or_row.get("review_minutes", 0.0)) * float(
        trace_or_row.get("review_rate_per_minute", 0.0)
    )
    cost = float(trace_or_row.get("cost_usd", machine + review))
    return {**trace_or_row, "cost_usd": cost}


def cost_per_outcome_by_plant(
    rows: Iterable[TraceRecord | dict[str, Any]],
    baseline_usd: dict[str, float] | None = None,
) -> list[PlantValueRow]:
    """Fully loaded cost divided by approved outcomes, normalized by severity."""

    groups: dict[tuple[str, str], dict[str, float | int]] = defaultdict(
        lambda: {"attempts": 0, "successes": 0, "cost": 0.0, "baseline": 0.0}
    )
    for raw in rows:
        row = _row(raw)
        key = (str(row["plant"]), str(row["severity"]))
        group = groups[key]
        group["attempts"] = int(group["attempts"]) + 1
        group["successes"] = int(group["successes"]) + int(
            row.get("outcome") == "approved"
        )
        group["cost"] = float(group["cost"]) + float(row["cost_usd"])
        row_baseline = (
            float(baseline_usd[key[1]])
            if baseline_usd is not None
            else float(row["baseline_usd"])
        )
        if float(group["baseline"]) not in {0.0, row_baseline}:
            raise ValueError(f"conflicting baselines for {key[0]} / {key[1]}")
        group["baseline"] = row_baseline

    report: list[PlantValueRow] = []
    for (plant, severity), group in sorted(groups.items()):
        attempts = int(group["attempts"])
        successes = int(group["successes"])
        rate = successes / attempts if attempts else 0.0
        low, high = wilson_interval(successes, attempts)
        per_outcome = float(group["cost"]) / successes if successes else None
        baseline = float(group["baseline"])
        verdict = (
            "no outcomes"
            if per_outcome is None
            else "below baseline"
            if per_outcome < baseline
            else "above baseline"
        )
        report.append(
            PlantValueRow(
                plant=plant,
                severity=severity,
                attempts=attempts,
                successes=successes,
                success_rate=round(rate, 4),
                ci_95_low=round(low, 4),
                ci_95_high=round(high, 4),
                cost_per_outcome_usd=(
                    round(per_outcome, 2) if per_outcome is not None else None
                ),
                baseline_usd=baseline,
                verdict=verdict,
            )
        )
    return report


def _trace_has_loop(trace: TraceRecord) -> bool:
    calls: set[tuple[str | None, str | None]] = set()
    for span in trace.spans:
        if span.kind == "guardrail" and span.attributes.get("reason") == "loop":
            return True
        if span.kind != "tool":
            continue
        key = (span.tool_name, span.arguments_hash)
        if key in calls:
            return True
        calls.add(key)
    return False


def production_metrics(traces: Sequence[TraceRecord]) -> dict[str, Any]:
    """Compute the paired production metric set from priced spans."""

    attempts = len(traces)
    successes = sum(trace.approved for trace in traces)
    step_counts = [
        sum(span.kind in {"generation", "tool", "handoff"} for span in trace.spans)
        for trace in traces
    ]
    tool_spans = [
        span for trace in traces for span in trace.spans if span.kind == "tool"
    ]
    generations = [
        span for trace in traces for span in trace.spans if span.kind == "generation"
    ]
    total_input = sum(span.usage.input_tokens for span in generations if span.usage)
    cached_input = sum(
        span.usage.cached_input_tokens for span in generations if span.usage
    )
    machine_cost = sum(trace.machine_cost_usd for trace in traces)
    human_cost = sum(trace.human_cost_usd for trace in traces)
    total_cost = machine_cost + human_cost
    low, high = wilson_interval(successes, attempts)
    return {
        "attempts": attempts,
        "approved_outcomes": successes,
        "success_rate": round(successes / attempts, 4) if attempts else 0.0,
        "success_rate_ci_95": [round(low, 4), round(high, 4)],
        "steps_per_task_p50": round(percentile(step_counts, 0.50), 2),
        "steps_per_task_p95": round(percentile(step_counts, 0.95), 2),
        "tool_failure_rate": round(
            sum(span.status == "error" for span in tool_spans) / len(tool_spans), 4
        )
        if tool_spans
        else 0.0,
        "retry_count": sum(
            max(0, int(span.attributes.get("attempt", 1)) - 1) for span in tool_spans
        ),
        "loop_rate": round(
            sum(_trace_has_loop(trace) for trace in traces) / attempts, 4
        )
        if attempts
        else 0.0,
        "handoff_count": sum(
            span.kind == "handoff" for trace in traces for span in trace.spans
        ),
        "cache_hit_rate": round(cached_input / total_input, 4) if total_input else 0.0,
        "machine_cost_usd": round(machine_cost, 4),
        "human_review_cost_usd": round(human_cost, 4),
        "fully_loaded_cost_usd": round(total_cost, 4),
        "cost_per_successful_outcome_usd": round(total_cost / successes, 2)
        if successes
        else None,
        "policy_denials": sum(
            span.kind == "guardrail" and span.attributes.get("reason") == "policy"
            for trace in traces
            for span in trace.spans
        ),
        "model_refusals": sum(
            span.kind == "generation"
            and span.attributes.get("finish_reason") == "refusal"
            for trace in traces
            for span in trace.spans
        ),
        "budget_stops": sum(trace.stop_reason is not None for trace in traces),
    }
