"""Allowlisted counterparties and the failure policy attached to each one."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


class RemoteAgentClient(Protocol):
    async def send_task(self, *, skill: str, payload: str, idempotency_key: str): ...


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    clock: Callable[[], float] = time.monotonic
    failures: int = 0
    state: str = "closed"
    opened_at: float | None = None

    def before_call(self) -> None:
        if self.state != "open":
            return
        assert self.opened_at is not None
        if self.clock() - self.opened_at >= self.recovery_timeout_seconds:
            self.state = "half_open"
            return
        raise CircuitOpenError("counterparty circuit breaker is open")

    def record_success(self) -> None:
        self.failures = 0
        self.state = "closed"
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.failure_threshold:
            self.state = "open"
            self.opened_at = self.clock()


@dataclass
class CounterpartyEntry:
    id: str
    display_name: str
    commodity_codes: set[str]
    client_factory: Callable[[], RemoteAgentClient]
    card_version: str
    contract_reference: str
    approved_by: str
    sla_seconds: float = 5.0
    supplier_score: float = 1.0
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def client(self) -> RemoteAgentClient:
        return self.client_factory()


class CounterpartyRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, CounterpartyEntry] = {}

    def register(self, entry: CounterpartyEntry) -> None:
        if entry.id in self._entries:
            raise ValueError(f"counterparty already registered: {entry.id}")
        self._entries[entry.id] = entry

    def require(self, counterparty_id: str) -> CounterpartyEntry:
        try:
            return self._entries[counterparty_id]
        except KeyError as exc:
            raise KeyError(
                f"counterparty is not allowlisted: {counterparty_id}"
            ) from exc

    def approved_for(self, commodity: str) -> list[CounterpartyEntry]:
        return [
            entry
            for entry in self._entries.values()
            if commodity in entry.commodity_codes
        ]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


COUNTERPARTIES = CounterpartyRegistry()
