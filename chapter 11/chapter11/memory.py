"""Memory hygiene with provenance, separate forgetting scores, and rollback."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from copy import deepcopy
from typing import Literal

from pydantic import Field

from .artifacts import load_json
from .models import Rate, Record


class Memory(Record):
    memory_id: str
    subject: str
    fact: str
    source_ids: list[str]
    parent_ids: list[str] = Field(default_factory=list)
    kind: Literal["fact", "summary", "embedding", "archive", "backup"] = "fact"
    created_day: int = Field(ge=0)
    expires_day: int = Field(ge=0)
    verified_day: int | None = None
    status: Literal["active", "expired", "superseded", "quarantined", "review"] = (
        "active"
    )


class Merged(Record):
    fact: str
    source_ids: list[str]
    confidence: Rate


class MemoryStore:
    def __init__(self, records: list[Memory]):
        if len({m.memory_id for m in records}) != len(records):
            raise ValueError("memory IDs must be unique across storage tiers")
        self.records = {m.memory_id: m.model_copy(deep=True) for m in records}
        self.snapshots: list[dict[str, Memory]] = []
        self.erased_ids: set[str] = set()
        self.last_run: int | None = None

    @classmethod
    def from_fixture(cls) -> MemoryStore:
        return cls([Memory.model_validate(m) for m in load_json("memories.json")])

    def active(self) -> list[Memory]:
        return [
            m
            for m in self.records.values()
            if m.status == "active" and m.kind in ("fact", "summary")
        ]

    def snapshot(self) -> int:
        self.snapshots.append(deepcopy(self.records))
        return len(self.snapshots) - 1

    def restore(self, snapshot: int) -> None:
        self.records = deepcopy(self.snapshots[snapshot])
        self._remove_lineage(self.erased_ids)

    def _lineage(self, roots: set[str]) -> set[str]:
        affected = set(roots)
        records = list(self.records.values()) + [
            m for snapshot in self.snapshots for m in snapshot.values()
        ]
        while True:
            expanded = affected | {
                m.memory_id
                for m in records
                if m.memory_id in affected
                or affected.intersection(m.source_ids + m.parent_ids)
            }
            if expanded == affected:
                return affected
            affected = expanded

    def quarantine(self, source_or_memory_id: str) -> list[str]:
        affected = self._lineage({source_or_memory_id})
        found = []
        for m in self.records.values():
            if m.memory_id in affected:
                m.status = "quarantined"
                found.append(m.memory_id)
        return sorted(found)

    def _remove_lineage(self, roots: set[str]) -> list[str]:
        affected = self._lineage(roots)
        removed = set()
        for collection in [self.records, *self.snapshots]:
            for memory_id in list(collection):
                if memory_id in affected:
                    removed.add(memory_id)
                    del collection[memory_id]
        self.erased_ids.update(affected)
        return sorted(removed)

    def erase(self, source_or_memory_id: str) -> dict:
        """Erase the transitive lineage from this local store and all its snapshots."""
        removed = self._remove_lineage({source_or_memory_id})
        return {
            "removed": removed,
            "scope": "local records, archives, embeddings, backups, snapshots",
        }


def score(store: MemoryStore, probes: list[dict]) -> dict[str, float]:
    if not probes:
        raise ValueError("recall and forgetting probes are required")
    recall, forgetting = [], []
    for probe in probes:
        facts = {m.fact for m in store.active() if m.subject == probe["subject"]}
        recall.append(probe["expected"] in facts)
        forgetting.append(not facts.intersection(probe["forbidden"]))
    return {
        "recall": sum(recall) / len(recall),
        "forgetting": sum(forgetting) / len(forgetting),
    }


async def offline_merge(group: list[Memory]) -> Merged:
    """Exact duplicates only; useful for testing the harness without a model."""
    if len({(m.subject, m.fact) for m in group}) != 1:
        raise ValueError("only duplicates of one subject may be merged")
    return Merged(
        fact=group[0].fact,
        source_ids=sorted({s for m in group for s in m.source_ids}),
        confidence=1,
    )


async def hygiene_pass(
    store: MemoryStore,
    asset_register: dict[str, str],
    probes: list[dict],
    *,
    day: int,
    merge: Callable[[list[Memory]], Awaitable[Merged]] = offline_merge,
    verification_sample: int = 3,
    scorer: Callable = score,
) -> dict:
    if verification_sample < 1:
        raise ValueError("verification sample must be positive")
    if store.last_run is not None and day < store.last_run:
        raise ValueError("hygiene clock cannot run backwards")
    snapshot = store.snapshot()
    before = scorer(store, probes)
    stages = []
    verified = []
    try:
        for m in store.active():
            if m.expires_day <= day:
                m.status = "expired"
        stages.append("expire")
        for m in store.active():
            if not m.source_ids:
                store.quarantine(m.memory_id)
            elif m.subject in asset_register and m.fact != asset_register[m.subject]:
                m.status = "superseded"
        stages.append("supersede")
        groups = defaultdict(list)
        for m in store.active():
            groups[(m.subject, m.fact)].append(m)
        for group in groups.values():
            if len(group) < 2:
                continue
            merged = await merge([m.model_copy(deep=True) for m in group])
            expected_sources = {s for m in group for s in m.source_ids}
            if set(
                merged.source_ids
            ) != expected_sources or merged.fact != asset_register.get(
                group[0].subject
            ):
                for m in group:
                    store.quarantine(m.memory_id)
                continue
            if merged.confidence < 0.8:
                for m in group:
                    m.status = "review"
                continue
            merged_id = "merged:" + "+".join(sorted(m.memory_id for m in group))
            store.records[merged_id] = Memory(
                memory_id=merged_id,
                subject=group[0].subject,
                fact=merged.fact,
                source_ids=sorted(expected_sources),
                parent_ids=[m.memory_id for m in group],
                kind="summary",
                created_day=day,
                expires_day=min(m.expires_day for m in group),
            )
            for m in group:
                m.status = "superseded"
        stages.append("consolidate")
        # Oldest verification first makes the bounded sample rotate across runs.
        due = sorted(
            store.active(),
            key=lambda m: (
                m.verified_day if m.verified_day is not None else -1,
                m.memory_id,
            ),
        )
        for m in due[:verification_sample]:
            confirmed = asset_register.get(m.subject) == m.fact
            if confirmed:
                m.verified_day = day
            else:
                store.quarantine(m.memory_id)
            verified.append({"memory_id": m.memory_id, "confirmed": confirmed})
        stages.append("verify")
        after = scorer(store, probes)
        rolled_back = any(after[key] < before[key] for key in ("recall", "forgetting"))
        if rolled_back:
            store.restore(snapshot)
        else:
            store.last_run = day
        return {
            "before": before,
            "candidate_after": after,
            "rolled_back": rolled_back,
            "effective_after": scorer(store, probes),
            "stages": stages,
            "verified": verified,
        }
    except Exception:
        store.restore(snapshot)
        raise
