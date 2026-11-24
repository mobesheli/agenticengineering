"""The release gate: one decision rule, three ways of enforcing it.

The rule is the paired comparison from Chapter 7. The mode decides what a failing
result does to the pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Literal

from pydantic import BaseModel

Mode = Literal["monitor", "comment", "block"]


class EvalResult(BaseModel):
    """What every evaluation suite reports, whichever framework produced it."""

    bundle: str
    suite: str
    trials: int
    cached: bool
    outcomes: dict[str, list[bool]]
    tokens: int

    def passed(self) -> dict[str, bool]:
        """A task counts only if every one of its trials passed."""
        return {task: all(trials) for task, trials in self.outcomes.items()}

    def score(self) -> float:
        return mean(self.passed().values())


@dataclass(frozen=True)
class Decision:
    verdict: Literal["pass", "warn", "block"]
    reason: str


def paired_drop(baseline: EvalResult, candidate: EvalResult) -> tuple[float, float]:
    """Mean fall in pass^k from baseline to candidate, with its standard error."""
    before, after = baseline.passed(), candidate.passed()
    drops = [float(before[task]) - float(after[task]) for task in before]
    return mean(drops), stdev(drops) / math.sqrt(len(drops))


def decide(
    baseline: EvalResult, candidate: EvalResult, floor: float, release: bool
) -> Decision:
    if set(candidate.outcomes) != set(baseline.outcomes):
        return Decision("block", "the two runs cover different tasks")
    if release and candidate.cached:
        return Decision("block", "a cached run cannot certify a release")
    if candidate.score() < floor:
        return Decision("block", f"score is below the {floor:.0%} floor")
    drop, standard_error = paired_drop(baseline, candidate)
    margin = 1.96 * standard_error
    if drop > margin:
        return Decision("block", f"quality fell {drop:.1%}, margin {margin:.1%}")
    if drop > 0:
        return Decision("warn", f"fell {drop:.1%}, inside the margin")
    return Decision("pass", "no fall against the baseline")


def enforce(decision: Decision, mode: Mode) -> tuple[int, str]:
    """Turn a decision into an exit code. Only block mode can stop a merge."""
    if mode == "monitor":
        return 0, "recorded only"
    if mode == "comment":
        return 0, "posted as a comment"
    return (1 if decision.verdict == "block" else 0), "enforced"
