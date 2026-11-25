"""The memory hygiene pass on day 180, scored before and after.

python -m examples.hygiene
"""

import asyncio

from chapter11.memory import Memory, MemoryStore, consolidator, hygiene_pass
from chapter11.settings import load
from examples.scripted import COMPRESSOR, merges


def build(name: str = "memories") -> tuple[MemoryStore, dict]:
    data = load(name)
    memories = {}
    for row in data["memories"]:
        row = {**row, "derived_from": tuple(row.get("derived_from", ()))}
        memories[row["id"]] = Memory(**row)
    store = MemoryStore(
        memories=memories,
        assets=data.get("assets", {}),
        today=data["today"],
        last_run=data.get("last_run", 0),
        embeddings=set(data.get("embeddings", [])),
        archive=dict(data.get("archive", {})),
        backups=dict(data.get("backups", {})),
    )
    return store, data


async def main() -> None:
    store, data = build()
    answer = store.retrieve("pump-P3-feed")
    print(f"before: asked about the feed pump, the agent reads {answer.id}")
    print(f"  {answer.text}")
    agent = consolidator(merges(COMPRESSOR))
    result = await hygiene_pass(store, data["probes"], data["ttl_days"], agent)
    for step in ("expired", "superseded", "merged", "quarantined", "flagged"):
        print(f"  {step:<12} {result[step]}")
    print(f"  {'unconfirmed':<12} {result['unconfirmed']}")
    (r0, f0), (r1, f1) = result["before"], result["after"]
    print(f"recall      {r0:.0%} before, {r1:.0%} after")
    print(f"forgetting  {f0:.0%} before, {f1:.0%} after")
    answer = store.retrieve("pump-P3-feed")
    print(f"after: asked about the feed pump, the agent reads {answer.id}")
    print(f"  {answer.text}")
    waiting = [
        m.id for m in store.memories.values() if m.status == "quarantined"
    ]
    print(f"waiting for a person: {', '.join(waiting)} (no source on record)")
    for line in store.log:
        print(line)


if __name__ == "__main__":
    asyncio.run(main())
