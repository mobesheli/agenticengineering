"""The counterparty registry: who we trust, on what evidence, and how we wait."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from a2a.types import AgentCard, TaskPushNotificationConfig
from a2a.utils.signing import create_signature_verifier
from jwt.exceptions import InvalidKeyError


class CircuitOpenError(RuntimeError):
    pass


class NotApproved(KeyError):
    pass


@dataclass(frozen=True)
class SigningKey:
    kid: str
    public_pem: str
    not_before: date
    not_after: date
    revoked: bool = False

    def usable_on(self, day: date) -> bool:
        return not self.revoked and self.not_before <= day <= self.not_after


@dataclass(frozen=True)
class TrustRecord:
    organization: str
    agent_url: str
    card_version: str
    card_fingerprint: str
    signing_keys: tuple[SigningKey, ...]
    trust_anchor: str
    contract_reference: str
    approved_by: str
    approved_on: date

    def verifier(self, today: date | None = None) -> Callable[[AgentCard], None]:
        day = today or date.today()
        keys = {key.kid: key for key in self.signing_keys}

        def key_for(kid: str | None, _jku: str | None) -> str:
            key = keys.get(kid or "")
            if key is None or not key.usable_on(day):
                raise InvalidKeyError(f"signing key is not trusted today: {kid}")
            return key.public_pem

        return create_signature_verifier(key_for, algorithms=["ES256"])


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_seconds: float = 30.0
    clock: Callable[[], float] = time.monotonic
    failures: int = 0
    state: str = "closed"
    opened_at: float | None = None

    def before_call(self) -> None:
        if self.state != "open":
            return
        if self.clock() - (self.opened_at or 0.0) >= self.recovery_seconds:
            self.state = "half_open"
            return
        raise CircuitOpenError("counterparty circuit breaker is open")

    def record_success(self) -> None:
        self.failures, self.state, self.opened_at = 0, "closed", None

    def record_failure(self) -> None:
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.failure_threshold:
            self.state, self.opened_at = "open", self.clock()


@dataclass
class CounterpartyEntry:
    id: str
    trust: TrustRecord
    commodity_codes: frozenset[str]
    sla_seconds: float = 5.0
    supplier_score: float = 1.0
    webhook: TaskPushNotificationConfig | None = None
    breaker: CircuitBreaker = field(default_factory=CircuitBreaker)


class CounterpartyRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, CounterpartyEntry] = {}

    def onboard(self, entry: CounterpartyEntry) -> None:
        if entry.id in self._entries:
            raise ValueError(f"counterparty already registered: {entry.id}")
        if not entry.trust.approved_by or not entry.trust.contract_reference:
            raise ValueError("an entry needs a named approver and a contract")
        if not entry.trust.signing_keys:
            raise ValueError("an entry needs at least one signing key")
        self._entries[entry.id] = entry

    def require(self, counterparty_id: str) -> CounterpartyEntry:
        try:
            return self._entries[counterparty_id]
        except KeyError:
            raise NotApproved(
                f"counterparty is not in the registry: {counterparty_id}"
            ) from None

    def approved_for(self, commodity: str) -> list[CounterpartyEntry]:
        return [e for e in self._entries.values() if commodity in e.commodity_codes]

    def clear(self) -> None:
        self._entries.clear()


COUNTERPARTIES = CounterpartyRegistry()
