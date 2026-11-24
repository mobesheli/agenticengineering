"""Park a run at an approval, then resume it in a different worker.

python -m examples.pause_resume --scripted     no API key needed
python -m examples.pause_resume                a live model, needs OPENAI_API_KEY
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from agents import set_tracing_disabled

from chapter10.bundle import load_bundle
from chapter10.planner import build_planner
from chapter10.worker import ParkedRuns, resume, run_turn
from examples.scripted import PLAN, closing, scripted_planner, staging

REQUEST = "Pump P-207 at plant 2 vibrates more every week. Plan the maintenance."


async def main(scripted_run: bool = True) -> list[str]:
    set_tracing_disabled(True)
    bundle, platform = load_bundle(), staging()
    release = bundle.bundle
    lines = []
    with tempfile.TemporaryDirectory() as folder:
        url = f"sqlite+aiosqlite:///{Path(folder) / 'runs.db'}"

        def worker(turns: list[list], session: str = "plant-2:planner-okafor"):
            if scripted_run:
                return scripted_planner(platform, bundle, session, turns)
            return build_planner(platform, bundle, session)

        store = await ParkedRuns.open(url)
        session = "plant-2:planner-okafor"
        first = await run_turn(worker(PLAN), store, session, REQUEST, release)
        lines.append(f"worker A, release {release}")
        lines.append(f"  status       {first['status']}")
        if first["status"] != "waiting":
            lines.append(f"  output       {first['output']}")
            print("\n".join(lines))
            return lines
        name, _, arguments = first["asks"][0].partition(" ")
        details = ", ".join(str(value) for value in json.loads(arguments).values())
        lines.append(f"  asks for     {name}: {details}")
        lines.append(f"  work orders  {len(platform.work_orders)}")
        await store.engine.dispose()

        store = await ParkedRuns.open(url)
        agent = worker(closing("The work order is created."))
        done = await resume(agent, store, first["run_id"], True, release)
        order = next(iter(platform.work_orders.values()))
        lines.append("worker B, a new process, after the planner approves")
        lines.append(f"  status       {done['status']}")
        lines.append(f"  output       {done['output']}")
        lines.append(f"  work orders  {len(platform.work_orders)} ({order['number']})")
        again = await resume(agent, store, first["run_id"], True, release)
        lines.append(
            f"  same approval sent twice: {again['status']}, {again['reason']}"
        )

        other = "plant-2:planner-lind"
        second = await run_turn(worker(PLAN, other), store, other, REQUEST, release)
        stale = await resume(
            agent, store, second["run_id"], True, "maintenance-planner@41.4"
        )
        lines.append("a second run waits while the release moves to 41.4")
        lines.append(f"  status       {stale['status']}, {stale['reason']}")
        lines.append(f"  work orders  {len(platform.work_orders)}")
        await store.engine.dispose()
    print("\n".join(lines))
    return lines


if __name__ == "__main__":
    asyncio.run(main("--scripted" in sys.argv))
