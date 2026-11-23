"""The task schema, and the golden and abuse tasks loaded from data/tasks.json."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

DATA = Path(__file__).resolve().parents[1] / "data"


class TaskKind(StrEnum):
    GOLDEN = "golden"
    ABUSE = "abuse"


class EvalTask(BaseModel):
    task_id: str
    kind: TaskKind
    instruction: str
    fixtures: dict[str, Any]
    expected: dict[str, str]
    checks: list[str]
    tags: list[str] = []
    reference_solution: str


def load_tasks(kind: TaskKind | None = None) -> list[EvalTask]:
    rows = json.loads((DATA / "tasks.json").read_text())
    tasks = [EvalTask.model_validate(row) for row in rows]
    return [task for task in tasks if kind is None or task.kind == kind]


def task_by_id(task_id: str) -> EvalTask:
    return next(task for task in load_tasks() if task.task_id == task_id)
