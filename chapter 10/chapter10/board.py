"""One operational board for built, joined, assembled, and bought agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import CHAPTER_ROOT, load_model
from .models import AgentEntry


def load_board(directory: Path | None = None) -> list[AgentEntry]:
    root = directory or CHAPTER_ROOT / "data/register/entries"
    return [load_model(path, AgentEntry) for path in sorted(root.glob("*.yaml"))]


def board_rows(entries: list[AgentEntry]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in entries:
        rows.append(
            {
                "agent": entry.agent,
                "owner": entry.owner,
                "route": entry.route,
                "progress": entry.status,
                "quality": entry.drift.get("outcome", "not observable"),
                "monthly_cost_usd": entry.budget.monthly_usd,
                "cost_source": entry.budget.source,
                "value_stage": entry.value_line.stage,
                "drift_signals": sum(
                    value not in (None, "not observable", "not reading")
                    for value in entry.drift.values()
                ),
                "drift_total": len(entry.drift),
            }
        )
    return rows


def write_board(
    path: Path, entries: list[AgentEntry] | None = None
) -> list[dict[str, Any]]:
    rows = board_rows(entries or load_board())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return rows
