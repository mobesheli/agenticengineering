"""Everything from this chapter wired together around the reconciliation agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from agents import Agent, Model

from chapter8.approvals import ApprovalBook
from chapter8.audit import DecisionLog, Notary
from chapter8.catalog import Catalog, description_problems, load_catalog
from chapter8.commit import Committer
from chapter8.gateway import EventLog, Gateway
from chapter8.phases import Parked
from chapter8.policy import WritePolicy, load_limits
from chapter8.reader import build_reader
from chapter8.records import RecordStore, load_patient
from chapter8.registry import Registry
from chapter8.review import Review, build_review
from chapter8.session import Session, Tokens
from chapter8.settings import fixed_clock
from chapter8.writer import build_writer

FIXTURES = (
    "patient-clean",
    "patient-hostile-note",
    "patient-canary",
    "patient-other",
)


class CatalogMismatch(Exception):
    """A tool the agent would load is not the tool the catalog approved."""


class Clock:
    """A clock the examples can move forward. Production uses the real one."""

    def __init__(self, start: Callable[[], datetime] = fixed_clock) -> None:
        self.now = start()

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@dataclass
class Harness:
    clock: Clock
    tokens: Tokens
    store: RecordStore
    catalog: Catalog
    registry: Registry
    events: EventLog
    gateway: Gateway
    book: ApprovalBook
    policy: WritePolicy
    log: DecisionLog
    notary: Notary
    committer: Committer

    @classmethod
    def build(cls, key: bytes = b"example-notary-key") -> Harness:
        clock = Clock()
        tokens = Tokens(clock)
        store = RecordStore(
            [load_patient(name) for name in FIXTURES], tokens, clock
        )
        catalog, registry, events = (
            load_catalog(),
            Registry.load(),
            EventLog(clock),
        )
        gateway = Gateway(catalog, registry, tokens, events, clock)
        limits = load_limits()
        book = ApprovalBook(ttl=timedelta(hours=limits.approval_ttl_hours))
        policy = WritePolicy(gateway, book, limits)
        log = DecisionLog()
        committer = Committer(gateway, policy, store, book, log)
        return cls(
            clock,
            tokens,
            store,
            catalog,
            registry,
            events,
            gateway,
            book,
            policy,
            log,
            Notary(key),
            committer,
        )

    def _checked(self, agent: Agent[Session]) -> Agent[Session]:
        problems = description_problems(self.catalog, agent.tools)
        if problems:
            raise CatalogMismatch("; ".join(problems))
        return agent

    def reader(self, model: str | Model | None = None) -> Agent[Session]:
        return self._checked(build_reader(self.gateway, self.store, model))

    def writer(self, model: str | Model | None = None) -> Agent[Session]:
        return self._checked(build_writer(self.gateway, self.committer, model))

    def review(self, parked: Parked, clinician: str) -> Review:
        return build_review(parked, self.store, clinician)

    def approve(
        self, parked: Parked, approver: str, role: str = "clinician"
    ) -> bool:
        """Record a signature for each approvable ask. The agent has no path here."""
        signed = False
        for ask in parked.asks:
            if not ask.problem:
                self.book.grant(ask.digest, approver, role, self.clock())
                self.events.append(
                    "approval_granted", approver, "review", ask.digest
                )
                signed = True
        return signed
