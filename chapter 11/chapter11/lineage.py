"""Lineage: from one source to every copy of what it became.

Two questions use the same walk. After a poisoned source: what else did this
produce? After an erasure request: where does every copy live, and what was done
with each?
"""

from __future__ import annotations

from chapter11.memory import MemoryStore


def lineage(store: MemoryStore, source_ids: set[str]) -> list[str]:
    """Every memory written from these sources, and everything derived."""
    found = [
        m.id
        for m in store.memories.values()
        if m.source_id and set(m.source_id.split(",")) & source_ids
    ]
    grew = True
    while grew:
        more = [
            m.id
            for m in store.memories.values()
            if m.id not in found and set(m.derived_from) & set(found)
        ]
        found += more
        grew = bool(more)
    return found


def quarantine(store: MemoryStore, source_ids: set[str]) -> list[str]:
    ids = lineage(store, source_ids)
    store.set_status([store.memories[i] for i in ids], "quarantined")
    return ids


def erase(store: MemoryStore, source_ids: set[str], retain: dict) -> dict:
    """Apply a decision to every copy, and return the record of what was done.

    `retain` maps a memory id to the legal basis for keeping it. A retained
    record is restricted: it stays, and retrieval can no longer return it.
    """
    record = {"deleted": [], "restricted": {}, "archive": [], "backups": {}}
    for memory_id in lineage(store, source_ids):
        if memory_id in retain:
            store.memories[memory_id].status = "restricted"
            record["restricted"][memory_id] = retain[memory_id]
            continue
        del store.memories[memory_id]
        store.embeddings.discard(memory_id)
        store.tombstones.add(memory_id)
        record["deleted"].append(memory_id)
        if store.archive.pop(memory_id, None) is not None:
            record["archive"].append(memory_id)
    for name, ids in store.backups.items():
        held = sorted(set(ids) & store.tombstones)
        if held:
            record["backups"][name] = held
    return record


def restore_backup(store: MemoryStore, name: str, saved: dict) -> list[str]:
    """Bring a backup back without bringing back what was erased."""
    blocked = sorted(set(store.backups[name]) & store.tombstones)
    for memory_id in store.backups[name]:
        current = store.memories.get(memory_id)
        if memory_id in store.tombstones or memory_id not in saved:
            continue
        if current is None or current.status != "restricted":
            store.memories[memory_id] = saved[memory_id]
    return blocked
