"""Fresh, fixture-backed state for each independent evaluation trial."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from typing import Any

from .models import EvalTask

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


class EvalEnvironment:
    def __init__(self, fixtures: dict[str, Any]) -> None:
        self.fixtures = copy.deepcopy(fixtures)
        self.state: dict[str, Any] = {"verdict": None, "route": None}
        self.closed = False

    def require_open(self) -> None:
        if self.closed:
            raise RuntimeError("trial environment has already been torn down")

    async def snapshot(self) -> dict[str, Any]:
        self.require_open()
        await asyncio.sleep(0)
        return copy.deepcopy(self.state)


def _read_fixture(relative_path: str, data_root: Path) -> Any:
    path = (data_root / relative_path).resolve()
    root = data_root.resolve()
    if root not in path.parents:
        raise ValueError(f"fixture escapes the data root: {relative_path}")
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else text


async def provision(
    task: EvalTask, *, data_root: Path = DATA_ROOT
) -> EvalEnvironment:
    fixtures = {
        name: _read_fixture(relative_path, data_root)
        for name, relative_path in task.fixtures.items()
    }
    await asyncio.sleep(0)
    return EvalEnvironment(fixtures)


async def teardown(environment: EvalEnvironment) -> None:
    environment.fixtures.clear()
    environment.closed = True
    await asyncio.sleep(0)
