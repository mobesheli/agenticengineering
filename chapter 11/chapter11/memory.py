"""A memory store you can snapshot, clean, score, and trace.

Chapter 4 built the tiers. This module is what keeps them true for a year: a
scheduled pass in a fixed order, scored before and after, and able to undo
itself. The store is deliberately small and in memory, so that every step of the
pass can be read. Your own store needs the same operations.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from agents import Agent, Model, Runner
from pydantic import BaseModel

RANK = {"summary": 0, "fact": 1, "note": 2}
LIVE = "active"


@dataclass
class Memory:
    id: str
    subject: str
    kind: str
    text: str
    claims: dict[str, Any]
    day: int
    source_id: str | None = None
    derived_from: tuple[str, ...] = ()
    status: str = LIVE
    verified_day: int | None = None


class Claim(BaseModel):
    name: str
    value: str


class Merged(BaseModel):
    text: str
    claims: list[Claim]
    source_ids: list[str]


INSTRUCTIONS = (
    "You merge duplicate memories about one subject into one. Keep every "
    "source id you were given. Keep only claims the memories agree on, with "
    "the claim names and values exactly as given. Never merge memories about "
    "different assets or different people."
)


def describe(group: list[Memory]) -> str:
    """What the consolidator is shown: each source, its text, and its claims."""
    lines = []
    for memory in group:
        claims = ", ".join(f"{k}={v}" for k, v in memory.claims.items())
        lines.append(f"{memory.source_id}: {memory.text} [claims: {claims}]")
    return "\n".join(lines)


def consolidator(model: str | Model) -> Agent:
    return Agent(
        name="memory-consolidator",
        instructions=INSTRUCTIONS,
        model=model,
        output_type=Merged,
    )


def safe_to_merge(group: list[Memory], merged: Merged, record: dict) -> bool:
    """Checks that do not depend on the model's opinion of its own work."""
    sources = {m.source_id for m in group}
    kept_every_source = set(merged.source_ids) == sources
    truth = record or group[0].claims
    agrees = all(str(truth.get(c.name)) == c.value for c in merged.claims)
    members_agree = all(m.claims == group[0].claims for m in group)
    return kept_every_source and agrees and (bool(record) or members_agree)


@dataclass
class MemoryStore:
    memories: dict[str, Memory]
    assets: dict[str, dict]
    today: int
    last_run: int
    embeddings: set[str] = field(default_factory=set)
    archive: dict[str, str] = field(default_factory=dict)
    backups: dict[str, list[str]] = field(default_factory=dict)
    tombstones: set[str] = field(default_factory=set)
    log: list[str] = field(default_factory=list)

    def live(self) -> list[Memory]:
        return [m for m in self.memories.values() if m.status == LIVE]

    def retrieve(self, subject: str) -> Memory | None:
        found = [m for m in self.live() if m.subject == subject]
        found.sort(key=lambda m: (RANK.get(m.kind, 9), -m.day))
        return found[0] if found else None

    def snapshot(self) -> dict[str, Memory]:
        return copy.deepcopy(self.memories)

    def restore(self, snapshot: dict[str, Memory]) -> None:
        self.memories = copy.deepcopy(snapshot)
        self.log.append("restored the snapshot")

    def set_status(self, memories: list[Memory], status: str) -> None:
        for memory in memories:
            memory.status = status

    def expire(self, ttl_days: dict[str, int]) -> int:
        old = [
            m
            for m in self.live()
            if self.today - m.day > ttl_days.get(m.kind, 10**6)
        ]
        self.set_status(old, "expired")
        return len(old)

    def confirms(self, memory: Memory) -> bool:
        record = self.assets.get(memory.subject, {})
        return all(record.get(k) == v for k, v in memory.claims.items())

    def supersede(self) -> int:
        changed = {
            subject
            for subject, record in self.assets.items()
            if record["changed_day"] > self.last_run
        }
        stale = [
            m
            for m in self.live()
            if m.subject in changed and not self.confirms(m)
        ]
        self.set_status(stale, "superseded")
        return len(stale)

    def duplicate_groups(self) -> list[list[Memory]]:
        groups: dict[tuple[str, str], list[Memory]] = {}
        for memory in self.live():
            groups.setdefault((memory.subject, memory.kind), []).append(memory)
        return [group for group in groups.values() if len(group) > 1]

    def replace(self, group: list[Memory], merged: Merged) -> None:
        first = group[0]
        truth = self.assets.get(first.subject) or first.claims
        self.set_status(group, "merged")
        for memory in group:
            self.archive[memory.id] = memory.text
        new = Memory(
            id="+".join(m.id for m in group),
            subject=first.subject,
            kind=first.kind,
            text=merged.text,
            claims={c.name: truth[c.name] for c in merged.claims},
            day=self.today,
            source_id=",".join(sorted(merged.source_ids)),
            derived_from=tuple(m.id for m in group),
        )
        self.memories[new.id] = new

    def due_for_verification(self, every_days: int = 90) -> list[Memory]:
        return [
            m
            for m in self.live()
            if m.subject in self.assets
            and (
                m.verified_day is None
                or self.today - m.verified_day > every_days
            )
        ]

    def mark_verified(self, memory: Memory, confirmed: bool) -> None:
        memory.verified_day = self.today
        if not confirmed:
            memory.status = "unconfirmed"


def score(store: MemoryStore, probes: dict) -> tuple[float, float]:
    """Recall: the right answer comes back. Forgetting: the old one does not."""

    def top(subject: str) -> dict:
        memory = store.retrieve(subject)
        return memory.claims if memory else {}

    recall = [
        all(top(p["subject"]).get(k) == v for k, v in p["expect"].items())
        for p in probes["recall"]
    ]
    forgotten = [
        all(top(p["subject"]).get(k) != v for k, v in p["gone"].items())
        for p in probes["forgetting"]
    ]
    return sum(recall) / len(recall), sum(forgotten) / len(forgotten)


async def hygiene_pass(
    store: MemoryStore, probes: dict, ttl_days: dict, agent: Agent
) -> dict:
    snapshot = store.snapshot()
    before = score(store, probes)
    done = {"expired": store.expire(ttl_days), "superseded": store.supersede()}
    done.update(merged=0, quarantined=0, flagged=0, unconfirmed=0)
    for group in store.duplicate_groups():
        unsourced = [memory for memory in group if memory.source_id is None]
        store.set_status(unsourced, "quarantined")
        done["quarantined"] += len(unsourced)
        group = [memory for memory in group if memory.source_id]
        if len(group) < 2:
            continue
        merged = (await Runner.run(agent, describe(group))).final_output
        if safe_to_merge(group, merged, store.assets.get(group[0].subject, {})):
            store.replace(group, merged)
            done["merged"] += 1
        else:
            store.set_status(group, "flagged for review")
            done["flagged"] += len(group)
    for memory in store.due_for_verification():
        confirmed = store.confirms(memory)
        store.mark_verified(memory, confirmed)
        done["unconfirmed"] += not confirmed
    after = score(store, probes)
    if after[0] < before[0] or after[1] < before[1]:
        store.restore(snapshot)
        done["restored"] = True
    store.last_run = store.today
    return {"before": before, "after": after, **done}
