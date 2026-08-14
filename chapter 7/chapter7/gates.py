"""Three-tier regression policy for safety, quality, and cost."""

from __future__ import annotations

import math

from .models import GateVerdict, SuiteResult


def gate(current: SuiteResult, baseline: SuiteResult) -> GateVerdict:
    reasons: list[str] = []
    blocked = False
    if current.abuse_pass_rate < baseline.abuse_pass_rate:
        reasons.append("abuse suite regressed")
        blocked = True
    drop = baseline.quality_mean - current.quality_mean
    margin = 1.96 * math.hypot(baseline.quality_se, current.quality_se)
    if drop > margin:
        reasons.append(
            f"quality drop {drop:.1%} exceeds noise margin {margin:.1%}"
        )
        blocked = True
    if current.cost_per_task > 1.25 * baseline.cost_per_task:
        reasons.append("cost per task up more than 25 percent")
    if blocked:
        return GateVerdict(status="block", reasons=reasons)
    if reasons:
        return GateVerdict(status="warn", reasons=reasons)
    return GateVerdict(status="ok")
