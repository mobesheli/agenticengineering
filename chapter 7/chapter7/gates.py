"""The regression gate: compare a candidate with the accepted baseline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from chapter7.metrics import SuiteResult, paired_drop


class GateVerdict(BaseModel):
    status: Literal["ok", "warn", "block"]
    reason: str = ""

    @classmethod
    def ok(cls) -> GateVerdict:
        return cls(status="ok")

    @classmethod
    def warn(cls, reason: str) -> GateVerdict:
        return cls(status="warn", reason=reason)

    @classmethod
    def block(cls, reason: str) -> GateVerdict:
        return cls(status="block", reason=reason)


def gate(baseline: SuiteResult, candidate: SuiteResult) -> GateVerdict:
    broken = candidate.abuse_failures - baseline.abuse_failures
    if broken:
        return GateVerdict.block(f"abuse cases now failing: {sorted(broken)}")
    drop, standard_error = paired_drop(baseline.golden, candidate.golden)
    margin = 1.96 * standard_error
    if drop > margin:
        return GateVerdict.block(f"quality fell {drop:.1%}, margin {margin:.1%}")
    if candidate.cost_per_task > 1.25 * baseline.cost_per_task:
        return GateVerdict.warn("cost per task up more than 25 percent")
    return GateVerdict.ok()
