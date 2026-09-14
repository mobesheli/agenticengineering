"""Fail-closed, per-run budgets enforced before metered actions."""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .models import NormalizedUsage, PriceCard
from .pricing import canonical_json, price_model_usage


class BudgetError(RuntimeError):
    """Base class for deterministic run-budget failures."""


class BudgetExhausted(BudgetError):
    pass


class LoopDetected(BudgetError):
    pass


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    action: str
    estimated_usd: float


class RunBudget:
    """A subtractive allowance shared by a run and its child delegations.

    Reservations happen before work. Settlement replaces an estimate with the
    observed cost. A child receives no more than the parent's remaining allowance.
    """

    def __init__(
        self,
        *,
        price_card: PriceCard,
        limit_usd: float,
        max_calls: int,
        max_steps: int,
        max_seconds: float,
        clock: Any = time.monotonic,
        parent: RunBudget | None = None,
    ) -> None:
        if limit_usd <= 0 or max_calls < 1 or max_steps < 1 or max_seconds <= 0:
            raise ValueError("budget limits must be positive")
        self.price_card = price_card
        self.limit_usd = float(limit_usd)
        self.max_calls = max_calls
        self.max_steps = max_steps
        self.max_seconds = float(max_seconds)
        self.clock = clock
        self.parent = parent
        self.started_at = float(clock())
        self.spent_usd = 0.0
        self.reserved_usd = 0.0
        self.calls = 0
        self.steps = 0
        self.stop_reason: str | None = None
        self._reservations: dict[str, Reservation] = {}
        self._seen_calls: set[str] = set()
        self._reserved_child_calls = 0
        self._reserved_child_steps = 0
        self._parent_hold: Reservation | None = None
        self._parent_call_allowance = 0
        self._parent_step_allowance = 0
        self._lock = threading.RLock()

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.limit_usd - self.spent_usd - self.reserved_usd)

    @property
    def remaining_calls(self) -> int:
        return max(0, self.max_calls - self.calls - self._reserved_child_calls)

    @property
    def remaining_steps(self) -> int:
        return max(0, self.max_steps - self.steps - self._reserved_child_steps)

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, float(self.clock()) - self.started_at)

    def _require_capacity(self, estimate: float, action: str) -> None:
        if self.stop_reason:
            raise BudgetExhausted(self.stop_reason)
        if self.elapsed_seconds >= self.max_seconds:
            self.stop_reason = "wall_clock_exhausted"
        elif self.remaining_calls < 1:
            self.stop_reason = "call_budget_exhausted"
        elif self.remaining_steps < 1:
            self.stop_reason = "step_budget_exhausted"
        elif estimate > self.remaining_usd + 1e-12:
            self.stop_reason = "cost_budget_exhausted"
        if self.stop_reason:
            raise BudgetExhausted(
                f"{self.stop_reason}: refused {action}; "
                f"spent=${self.spent_usd:.4f}, reserved=${self.reserved_usd:.4f}, "
                f"limit=${self.limit_usd:.4f}"
            )

    def reserve(self, action: str, estimate_usd: float) -> Reservation:
        if estimate_usd < 0:
            raise ValueError("reservation estimate cannot be negative")
        with self._lock:
            self._require_capacity(estimate_usd, action)
            reservation = Reservation(str(uuid4()), action, estimate_usd)
            self._reservations[reservation.reservation_id] = reservation
            self.reserved_usd += estimate_usd
            self.calls += 1
            self.steps += 1
            return reservation

    def reserve_model(self, model: str, usage_ceiling: object) -> Reservation:
        normalized = (
            usage_ceiling
            if isinstance(usage_ceiling, NormalizedUsage)
            else NormalizedUsage.model_validate(usage_ceiling)
        )
        estimate = price_model_usage(
            normalized, model=model, card=self.price_card
        ).total
        return self.reserve(f"model:{model}", estimate)

    def reserve_tool(self, tool_name: str, arguments: object) -> Reservation:
        fingerprint = self.call_fingerprint(tool_name, arguments)
        with self._lock:
            if fingerprint in self._seen_calls:
                raise LoopDetected(
                    f"exact tool call already ran: {tool_name}; reuse its recorded result"
                )
            estimate = self.price_card.tool_cost(tool_name)
            reservation = self.reserve(f"tool:{tool_name}", estimate)
            self._seen_calls.add(fingerprint)
            return reservation

    def settle(self, reservation: Reservation, actual_usd: float) -> None:
        if actual_usd < 0:
            raise ValueError("actual cost cannot be negative")
        with self._lock:
            stored = self._reservations.pop(reservation.reservation_id, None)
            if stored is None:
                raise KeyError(
                    "reservation was already settled or does not belong to this budget"
                )
            self.reserved_usd -= stored.estimated_usd
            self.spent_usd += actual_usd
            if self.spent_usd > self.limit_usd + 1e-12:
                self.stop_reason = "settlement_overshoot"

    def cancel(self, reservation: Reservation) -> None:
        with self._lock:
            stored = self._reservations.pop(reservation.reservation_id, None)
            if stored is None:
                raise KeyError("reservation was already resolved")
            self.reserved_usd -= stored.estimated_usd

    def child(self, *, limit_usd: float, max_calls: int, max_steps: int) -> RunBudget:
        with self._lock:
            try:
                self._require_capacity(limit_usd, "child_delegation")
            except BudgetExhausted as exc:
                raise BudgetExhausted(
                    "child cannot mint more than the parent's remainder"
                ) from exc
            if max_calls > self.remaining_calls or max_steps > self.remaining_steps:
                raise BudgetExhausted(
                    "child call and step limits must fit the parent remainder"
                )
            hold = Reservation(str(uuid4()), "child_allowance", limit_usd)
            self._reservations[hold.reservation_id] = hold
            self.reserved_usd += limit_usd
            self._reserved_child_calls += max_calls
            self._reserved_child_steps += max_steps
            child = RunBudget(
                price_card=self.price_card,
                limit_usd=limit_usd,
                max_calls=max_calls,
                max_steps=max_steps,
                max_seconds=max(0.001, self.max_seconds - self.elapsed_seconds),
                clock=self.clock,
                parent=self,
            )
            child._parent_hold = hold
            child._parent_call_allowance = max_calls
            child._parent_step_allowance = max_steps
            return child

    def absorb_child(self, child: RunBudget) -> None:
        if child.parent is not self:
            raise ValueError("budget is not a child of this parent")
        if child.reserved_usd:
            raise BudgetError(
                "settle or cancel the child's outstanding calls before absorbing it"
            )
        with self._lock:
            hold = child._parent_hold
            if (
                hold is None
                or self._reservations.pop(hold.reservation_id, None) is None
            ):
                raise BudgetError("child allowance was already absorbed")
            self.reserved_usd -= hold.estimated_usd
            self._reserved_child_calls -= child._parent_call_allowance
            self._reserved_child_steps -= child._parent_step_allowance
            self.spent_usd += child.spent_usd
            self.calls += child.calls
            self.steps += child.steps
            child._parent_hold = None

    def record_stop(self, reason: str) -> None:
        with self._lock:
            self.stop_reason = reason

    def snapshot(self) -> dict[str, float | int | str | None]:
        return {
            "limit_usd": round(self.limit_usd, 6),
            "spent_usd": round(self.spent_usd, 6),
            "reserved_usd": round(self.reserved_usd, 6),
            "remaining_usd": round(self.remaining_usd, 6),
            "calls": self.calls,
            "remaining_calls": self.remaining_calls,
            "steps": self.steps,
            "remaining_steps": self.remaining_steps,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "stop_reason": self.stop_reason,
        }

    @staticmethod
    def call_fingerprint(tool_name: str, arguments: object) -> str:
        payload = f"{tool_name}:{canonical_json(arguments)}".encode()
        return hashlib.sha256(payload).hexdigest()
