"""Cost alert thresholds and explicit anomaly-detector coverage."""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from .models import TraceRecord


def credit_depletion_state(spent_usd: float, limit_usd: float) -> dict[str, Any]:
    if spent_usd < 0 or limit_usd <= 0:
        raise ValueError("credit amounts must be non-negative and the limit positive")
    remaining_fraction = max(0.0, 1 - spent_usd / limit_usd)
    status = (
        "exhausted"
        if spent_usd >= limit_usd
        else "page"
        if remaining_fraction <= 0.20
        else "warn"
        if remaining_fraction <= 0.50
        else "ok"
    )
    return {
        "status": status,
        "spent_usd": round(spent_usd, 4),
        "limit_usd": round(limit_usd, 4),
        "remaining_fraction": round(remaining_fraction, 4),
    }


def detector_coverage(
    detectors: dict[str, Sequence[str]],
    *,
    required_dimensions: Sequence[str],
) -> dict[str, Any]:
    covered = {dimension for values in detectors.values() for dimension in values}
    missing = sorted(set(required_dimensions) - covered)
    return {
        "status": "gap" if missing else "covered",
        "missing_dimensions": missing,
        "detectors": {name: sorted(set(values)) for name, values in detectors.items()},
    }


def robust_cost_anomalies(
    traces: Sequence[TraceRecord],
    *,
    median_absolute_deviations: float = 4.0,
) -> list[dict[str, Any]]:
    """Flag high trace costs within the same plant and severity workload."""

    if median_absolute_deviations <= 0:
        raise ValueError("the anomaly multiplier must be positive")
    groups: dict[tuple[str, str], list[TraceRecord]] = defaultdict(list)
    for trace in traces:
        groups[(trace.identity.plant, trace.severity)].append(trace)
    anomalies = []
    for (plant, severity), rows in sorted(groups.items()):
        costs = [row.fully_loaded_cost_usd for row in rows]
        median = statistics.median(costs)
        mad = statistics.median(abs(value - median) for value in costs)
        threshold = median + median_absolute_deviations * mad
        if mad == 0:
            threshold = median * 2
        for row in rows:
            if row.fully_loaded_cost_usd > threshold:
                anomalies.append(
                    {
                        "trace_id": row.trace_id,
                        "owner": row.identity.owner,
                        "workload": row.identity.workflow,
                        "plant": plant,
                        "severity": severity,
                        "cost_usd": round(row.fully_loaded_cost_usd, 4),
                        "threshold_usd": round(threshold, 4),
                    }
                )
    return anomalies
