"""The run budget: an allowance that is reserved before each metered action."""

from __future__ import annotations

from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    """The next action would take the run past its allowance. The run stops."""

    def __init__(self, reason: str, budget: RunBudget, wanted: float) -> None:
        self.reason, self.wanted = reason, wanted
        self.spent, self.limit = budget.spent_usd, budget.limit_usd
        super().__init__(
            f"{reason}: spent ${self.spent:.4f} of ${self.limit:.2f}, "
            f"next action needs ${wanted:.4f}"
        )


@dataclass
class RunBudget:
    limit_usd: float
    model_calls: int = 12
    tool_calls: int = 12
    first_call_usd: float = 0.03
    parent: RunBudget | None = None
    spent_usd: float = 0.0
    reserved_usd: float = 0.0
    largest_call_usd: float = 0.0
    seen: set[tuple[str, str]] = field(default_factory=set)
    stops: list[str] = field(default_factory=list)

    @property
    def remaining_usd(self) -> float:
        own = self.limit_usd - self.spent_usd - self.reserved_usd
        return (
            own if self.parent is None else min(own, self.parent.remaining_usd)
        )

    def estimate(self) -> float:
        return max(self.largest_call_usd, self.first_call_usd)

    def reserve(self, usd: float, kind: str) -> None:
        left = self.model_calls if kind == "model" else self.tool_calls
        if left < 1:
            self.stop(f"no {kind} calls left", usd)
        if usd > self.remaining_usd + 1e-9:
            self.stop("run budget exhausted", usd)
        self._hold(usd)
        if kind == "model":
            self.model_calls -= 1
        else:
            self.tool_calls -= 1

    def settle(self, reserved: float, actual: float) -> None:
        self._hold(-reserved)
        self._spend(actual)
        self.largest_call_usd = max(self.largest_call_usd, actual)

    def child(self, limit_usd: float, **limits: int) -> RunBudget:
        return RunBudget(
            min(limit_usd, self.remaining_usd), parent=self, **limits
        )

    def repeated(self, tool: str, arguments: str) -> bool:
        key = (tool, arguments)
        if key in self.seen:
            return True
        self.seen.add(key)
        return False

    def stop(self, reason: str, wanted: float) -> None:
        self.stops.append(reason)
        raise BudgetExceeded(reason, self, wanted)

    def _hold(self, usd: float) -> None:
        self.reserved_usd += usd
        if self.parent is not None:
            self.parent._hold(usd)

    def _spend(self, usd: float) -> None:
        self.spent_usd += usd
        if self.parent is not None:
            self.parent._spend(usd)
