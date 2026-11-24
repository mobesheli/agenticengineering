"""Canary one plant, roll it back, and list what the rollback did not undo.

python -m examples.rollout_demo
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from agents import set_tracing_disabled

from chapter10.bundle import load_bundle
from chapter10.release import canary, left_behind, rollback
from chapter10.worker import ParkedRuns, resume, run_turn
from examples.scripted import PLAN, closing, scripted_planner, staging

REQUEST = "Pump P-207 at plant 2 vibrates more every week. Plan the maintenance."


def pointers(platform) -> str:
    return "  " + "  ".join(
        f"{p} {b.split('@')[1]}" for p, b in platform.endpoints.items()
    )


async def main() -> list[str]:
    set_tracing_disabled(True)
    bundle, platform = load_bundle(), staging()
    new, old = bundle.bundle, "maintenance-planner@41.2"
    lines = ["before", pointers(platform)]
    canary(platform, "plant-2", new)
    lines += [f"canary: plant-2 runs {new}", pointers(platform)]

    with tempfile.TemporaryDirectory() as folder:
        store = await ParkedRuns.open(f"sqlite+aiosqlite:///{Path(folder) / 'runs.db'}")
        first = await run_turn(
            scripted_planner(platform, bundle, "s1", PLAN), store, "s1", REQUEST, new
        )
        agent = scripted_planner(
            platform, bundle, "s1", closing("The work order is created.")
        )
        await resume(agent, store, first["run_id"], True, new)
        platform.memory_writes.append({"bundle": new, "schema": 4, "about": "P-207"})
        await run_turn(
            scripted_planner(platform, bundle, "s2", PLAN), store, "s2", REQUEST, new
        )

        rollback(platform, "plant-2", old)
        lines += [f"rollback: plant-2 returns to {old}", pointers(platform)]
        lines.append("what the rollback left behind")
        lines += [
            f"  {item}" for item in left_behind(platform, new, await store.statuses())
        ]
        await store.engine.dispose()
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    asyncio.run(main())
