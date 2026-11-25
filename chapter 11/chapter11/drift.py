"""The drift check: five signals in, one decision out."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    OK = "ok"
    HOLD = "hold"
    RERUN = "rerun the golden suite"
    PROPOSE = "propose a candidate"
    BUDGET = "budget review"


@dataclass(frozen=True)
class Reading:
    signal: str
    value: float
    baseline: float
    band: float

    @property
    def shift(self) -> float:
        return self.value - self.baseline

    @property
    def moved(self) -> bool:
        return abs(self.shift) > self.band


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    candidate: bool
    why: str


def decide(readings: list[Reading], changed: dict[str, tuple]) -> Verdict:
    moved = {r.signal: r.shift for r in readings if r.moved}
    if changed:
        what = ", ".join(sorted(changed))
        return Verdict(Decision.HOLD, True, f"not the approved bundle: {what}")
    if not moved:
        return Verdict(Decision.OK, False, "every signal inside its band")
    if "cost and speed" in moved:
        return Verdict(Decision.BUDGET, False, "cost or speed outside its band")
    if set(moved) == {"outcome"} and moved["outcome"] > 0:
        return Verdict(Decision.PROPOSE, True, "better, and nobody knows why")
    return Verdict(Decision.RERUN, False, "moved: " + ", ".join(sorted(moved)))
