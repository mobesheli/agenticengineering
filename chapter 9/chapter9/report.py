"""The reports both audiences read, computed from ledger records."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable

from chapter9.ledger import SUCCESS, RunRecord
from chapter9.pricecard import PriceCard


def direct_cost(run: RunRecord, card: PriceCard) -> dict[str, float]:
    """What one attempt cost directly: metered spend plus the reviewer's time."""
    return {
        "model tokens": run.model_usd,
        "tools and retrieval": run.tool_usd,
        "checks and sampled judge": card.overheads["checks"],
        "trace storage": card.overheads["trace_storage"],
        "human review": run.review_minutes * card.review_usd_per_minute,
    }


def wilson(
    successes: int, attempts: int, z: float = 1.96
) -> tuple[float, float]:
    """A 95% interval for a rate that behaves on small samples and at 0 or 1."""
    if attempts == 0:
        return 0.0, 1.0
    rate, z2 = successes / attempts, z * z
    center = (rate + z2 / (2 * attempts)) / (1 + z2 / attempts)
    spread = z * math.sqrt(rate * (1 - rate) / attempts + z2 / (4 * attempts**2))
    half = spread / (1 + z2 / attempts)
    return max(0.0, center - half), min(1.0, center + half)


def unit_cost(runs: list[RunRecord], card: PriceCard) -> dict:
    lines: dict[str, float] = defaultdict(float)
    for run in runs:
        for name, usd in direct_cost(run, card).items():
            lines[name] += usd / len(runs)
    approved = sum(run.outcome == SUCCESS for run in runs)
    attempt = sum(lines.values())
    return {
        "lines": dict(lines),
        "attempts": len(runs),
        "approved": approved,
        "per_attempt": attempt,
        "success_rate": approved / len(runs),
        "per_approved": attempt * len(runs) / approved if approved else None,
    }


def cost_per_outcome(
    runs: Iterable[RunRecord],
    card: PriceCard,
    baseline_usd: dict[str, float],
    by: tuple[str, ...] = ("plant", "severity"),
) -> list[dict]:
    groups: dict[tuple, dict] = defaultdict(
        lambda: {"attempts": 0, "approved": 0, "cost": 0.0, "baseline": 0.0}
    )
    for run in runs:
        group = groups[tuple(run.identity[key] for key in by)]
        group["attempts"] += 1
        group["approved"] += run.outcome == SUCCESS
        group["cost"] += sum(direct_cost(run, card).values())
        group["baseline"] += baseline_usd.get(run.identity["severity"], math.nan)
    report = []
    for key, group in sorted(groups.items()):
        attempts, approved = group["attempts"], group["approved"]
        low, high = wilson(approved, attempts)
        baseline = group["baseline"] / attempts
        per_order = group["cost"] / approved if approved else None
        report.append(
            {
                **dict(zip(by, key, strict=True)),
                "attempts": attempts,
                "approved": approved,
                "rate": approved / attempts,
                "rate_low": low,
                "rate_high": high,
                "usd_per_approved": per_order,
                "baseline_usd": None if math.isnan(baseline) else baseline,
                "verdict": verdict(group["cost"], attempts, low, high, baseline),
            }
        )
    return report


def verdict(
    cost: float, attempts: int, low: float, high: float, baseline: float
) -> str:
    """Compare with the baseline at both ends of the interval."""
    if math.isnan(baseline):
        return "no baseline"
    if low == 0.0:
        return "no reliable rate"
    best, worst = cost / (attempts * high), cost / (attempts * low)
    if worst < baseline:
        return "below baseline"
    return "above baseline" if best > baseline else "at baseline"


def token_share_by_step(runs: Iterable[RunRecord]) -> list[dict]:
    totals: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"calls": 0, "input": 0, "cached": 0, "reasoning": 0, "usd": 0.0}
    )
    for run in runs:
        for call in run.model_calls:
            row = totals[(call.step, call.model)]
            row["calls"] += 1
            row["input"] += call.input_tokens
            row["cached"] += call.cached_tokens
            row["reasoning"] += call.reasoning_tokens
            row["usd"] += call.cost_usd
    spent = sum(row["usd"] for row in totals.values()) or 1.0
    ranked = sorted(totals.items(), key=lambda item: -item[1]["usd"])
    return [
        {"step": step, "model": model, **row, "share": row["usd"] / spent}
        for (step, model), row in ranked
    ]


def percentile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


def metrics(runs: list[RunRecord]) -> dict[str, float]:
    tools = [call for run in runs for call in run.tool_calls]
    model = [call for run in runs for call in run.model_calls]
    looped = sum(
        any(call.repeat and not call.refused for call in run.tool_calls)
        for run in runs
    )
    refused = sum(any(call.refused for call in run.tool_calls) for run in runs)
    return {
        "turns_p50": percentile([run.turns for run in runs], 0.50),
        "turns_p95": percentile([run.turns for run in runs], 0.95),
        "loop_rate": looped / len(runs),
        "refused_repeat_rate": refused / len(runs),
        "tool_failure_rate": sum(call.failed for call in tools) / len(tools),
        "cache_hit_rate": sum(c.cached_tokens for c in model)
        / sum(c.input_tokens for c in model),
        "tokens_per_run": sum(run.tokens for run in runs) / len(runs),
    }


def reconcile(
    runs: list[RunRecord], invoice_usd: float, tolerance: float
) -> dict:
    ledger = sum(run.model_usd for run in runs)
    gap = (invoice_usd - ledger) / invoice_usd
    return {
        "ledger_usd": ledger,
        "invoice_usd": invoice_usd,
        "gap": gap,
        "within_tolerance": abs(gap) <= tolerance,
    }


def bill_change(earlier: dict, runs: list[RunRecord]) -> dict[str, float]:
    """Split a change in the token bill into runs, tokens per run, and price."""
    tokens = sum(run.tokens for run in runs)
    spend = sum(run.model_usd for run in runs)
    now = {
        "runs": len(runs),
        "tokens_per_run": tokens / len(runs),
        "usd_per_million_tokens": spend / tokens * 1_000_000,
    }
    change = {key: now[key] / earlier[key] for key in now}
    old_bill = math.prod(earlier[key] for key in now) / 1_000_000
    return {
        **{f"{key}_x": value for key, value in change.items()},
        "bill_before": old_bill,
        "bill_now": spend,
        "bill_x": spend / old_bill,
    }
