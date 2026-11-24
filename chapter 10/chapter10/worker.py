"""A worker that holds nothing between requests.

A run that stops at an approval is parked in a table the agent cannot write to.
Any worker can resume it later, under the release that produced it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from agents import Agent, Runner, RunState
from agents.extensions.memory import SQLAlchemySession
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

CREATE = """CREATE TABLE IF NOT EXISTS parked_runs (
    run_id TEXT PRIMARY KEY, session_id TEXT, bundle TEXT, state TEXT, status TEXT)"""
CLAIM = """UPDATE parked_runs SET status = 'claimed'
    WHERE run_id = :run_id AND status = 'waiting'
    RETURNING session_id, bundle, state"""


@dataclass
class Parked:
    session_id: str
    bundle: str
    state: str


class ParkedRuns:
    """The approval queue. One row for each run that is waiting for a decision."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @classmethod
    async def open(cls, url: str) -> ParkedRuns:
        """SQLite allows one writer, so a SQLite store uses one connection at a time."""
        one_writer = {"pool_size": 1, "max_overflow": 0}
        engine = create_async_engine(url, **(one_writer if "sqlite" in url else {}))
        async with engine.begin() as db:
            await db.execute(text(CREATE))
        return cls(engine)

    async def park(self, session_id: str, bundle: str, state: str) -> str:
        run_id = uuid.uuid4().hex[:12]
        row = {"r": run_id, "s": session_id, "b": bundle, "t": state}
        insert = "INSERT INTO parked_runs VALUES (:r, :s, :b, :t, 'waiting')"
        async with self.engine.begin() as db:
            await db.execute(text(insert), row)
        return run_id

    async def claim(self, run_id: str) -> Parked | None:
        """Take a waiting run. Only one caller can ever win a given run."""
        async with self.engine.begin() as db:
            row = (await db.execute(text(CLAIM), {"run_id": run_id})).first()
        return Parked(*row) if row else None

    async def close(self, run_id: str, status: str) -> None:
        update = "UPDATE parked_runs SET status = :s, state = '' WHERE run_id = :r"
        async with self.engine.begin() as db:
            await db.execute(text(update), {"s": status, "r": run_id})

    async def statuses(self) -> dict[str, str]:
        async with self.engine.begin() as db:
            rows = await db.execute(text("SELECT run_id, status FROM parked_runs"))
        return dict(rows.all())


def session_for(store: ParkedRuns, session_id: str) -> SQLAlchemySession:
    return SQLAlchemySession(session_id, engine=store.engine, create_tables=True)


async def run_turn(
    agent: Agent, store: ParkedRuns, session_id: str, text: str, bundle: str
) -> dict[str, Any]:
    session = session_for(store, session_id)
    result = await Runner.run(agent, text, session=session)
    if not result.interruptions:
        return {"status": "done", "output": result.final_output}
    asks = [f"{ask.name} {ask.arguments}" for ask in result.interruptions]
    run_id = await store.park(session_id, bundle, result.to_state().to_string())
    return {"status": "waiting", "run_id": run_id, "asks": asks}


async def resume(
    agent: Agent, store: ParkedRuns, run_id: str, approved: bool, bundle: str
) -> dict[str, Any]:
    parked = await store.claim(run_id)
    if parked is None:
        return {"status": "gone", "reason": "unknown run, or already decided"}
    if parked.bundle != bundle:
        await store.close(run_id, "stale")
        return {"status": "stale", "reason": "release moved while waiting"}
    state = await RunState.from_string(agent, parked.state)
    for request in state.get_interruptions():
        state.approve(request) if approved else state.reject(request)
    session = session_for(store, parked.session_id)
    result = await Runner.run(agent, state, session=session)
    await store.close(run_id, "approved" if approved else "rejected")
    return {"status": "done", "output": result.final_output}
