"""Checkpointing: resume a pipeline from the last completed step, not from zero."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Step:
    name: str
    run: Callable[[dict[str, Any], str], Awaitable[Any]]


class Checkpoints:
    """One row per completed step, written to a database that outlives the worker."""

    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints ("
            "run_id TEXT, step TEXT, output TEXT, PRIMARY KEY (run_id, step))"
        )

    def load(self, run_id: str) -> dict[str, Any]:
        rows = self.db.execute(
            "SELECT step, output FROM checkpoints WHERE run_id = ?", (run_id,)
        )
        return {step: json.loads(output) for step, output in rows}

    def save(self, run_id: str, step: str, output: Any) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?)",
            (run_id, step, json.dumps(output)),
        )
        self.db.commit()


async def run_pipeline(run_id: str, steps: list[Step], store: Checkpoints) -> dict:
    done = store.load(run_id)
    for step in steps:
        if step.name in done:
            continue
        idempotency_key = f"{run_id}:{step.name}"
        done[step.name] = await step.run(done, idempotency_key)
        store.save(run_id, step.name, done[step.name])
    return done
