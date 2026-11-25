"""One poisoned source traced, and one erasure request carried through.

python -m examples.lineage_demo
"""

from chapter11.lineage import erase, lineage, quarantine, restore_backup
from examples.hygiene import build


def main() -> None:
    store, data = build("lineage")
    saved = store.snapshot()
    source = data["poisoned_source"]
    ids = quarantine(store, {source})
    print(
        f"source {source} (contractor, unverified) produced {len(ids)} memories"
    )
    for memory_id in ids:
        memory = saved[memory_id]
        came = memory.source_id or "from " + ", ".join(memory.derived_from)
        print(f"  {memory_id}  {memory.kind:<8} {came:<12} quarantined")
    left = store.retrieve("plant-2-lockout")
    print(f"  what the agent can retrieve about plant 2 lockout now: {left}")

    sources = set(data["erasure_sources"])
    print(f"\nerasure request: sources {', '.join(sorted(sources))}")
    print(f"  copies found: {', '.join(lineage(store, sources))}")
    record = erase(store, sources, data["retain"])
    print(
        f"  deleted from the store and the index: {', '.join(record['deleted'])}"
    )
    print(
        f"  deleted from the archive of originals: {', '.join(record['archive'])}"
    )
    for memory_id, basis in record["restricted"].items():
        print(f"  kept and restricted: {memory_id}")
        print(f"    basis: {basis}")
    for name, held in record["backups"].items():
        print(f"  backup {name} still holds {', '.join(held)}: marked")
    blocked = restore_backup(store, "weekly-22", saved)
    print(
        f"restoring weekly-22 later: {', '.join(blocked)} are not brought back"
    )
    hidden = store.retrieve("press-03-inspection") is None
    print(f"  the retained record is still hidden from retrieval: {hidden}")


if __name__ == "__main__":
    main()
