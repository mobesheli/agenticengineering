"""A fresh environment for every trial, built from the task's fixtures."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from chapter7.tasks import DATA, EvalTask

POLICY_TEXT = (DATA / "policy" / "approvals_v7.md").read_text()
CLAUSES = dict(re.findall(r"^(AP-\d+\.\d+): (.+)$", POLICY_TEXT, flags=re.MULTILINE))


@dataclass
class ReviewEnvironment:
    """Everything one trial can read and change. Nothing is shared between trials."""

    task: EvalTask
    trial_index: int
    entry: dict[str, Any]
    history: list[str]
    state: dict[str, Any] = field(
        default_factory=lambda: {
            "verdict": None,
            "route": None,
            "rationale": "",
            "cited_clauses": [],
            "posted": False,
            "amended": False,
        }
    )
    document_reads: int = 0

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)


def provision(task: EvalTask, trial_index: int = 0) -> ReviewEnvironment:
    fixtures = copy.deepcopy(task.fixtures)
    return ReviewEnvironment(
        task=task,
        trial_index=trial_index,
        entry=fixtures["entry"],
        history=fixtures.get("history", []),
    )
