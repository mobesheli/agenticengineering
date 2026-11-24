"""The board: one row for each agent, read from the register and its records."""

from __future__ import annotations

import json
from pathlib import Path

from chapter10.gate import EvalResult
from chapter10.register import LADDERS, Entry

SIGNALS = ["model", "input", "knowledge", "outcome", "cost"]


def stage_cell(entry: Entry) -> str:
    ladder = LADDERS[entry.route]
    return f"{entry.status} {ladder.index(entry.status) + 1}/{len(ladder)}"


def quality_cell(entry: Entry, repo: Path) -> str:
    path = repo / entry.evidence.get("eval_report", "missing")
    if not path.is_file():
        return "no report: run the gate"
    report = EvalResult.model_validate_json(path.read_bytes())
    return f"{report.score():.0%} of {len(report.outcomes)} tasks"


def cost_cell(entry: Entry) -> str:
    amount, source = entry.budget.get("last_month_usd"), entry.budget["source"]
    if amount is None:
        return "not metered"
    return f"${amount:,} {source}"


def drift_cell(entry: Entry, repo: Path) -> str:
    if not entry.monitoring or not (repo / entry.monitoring).is_file():
        return "not configured"
    signals = json.loads((repo / entry.monitoring).read_text())["signals"]
    reporting = sum(signals[name]["status"] in ("ok", "alert") for name in SIGNALS)
    alerts = sum(signals[name]["status"] == "alert" for name in SIGNALS)
    return f"{reporting} of 5" + (f", {alerts} alert" if alerts else "")


def board(entries: list[Entry], repo: Path) -> list[str]:
    header = f"{'agent':21}{'route':9}{'stage':16}{'quality':18}{'value':11}drift"
    lines = [header]
    for entry in entries:
        lines.append(
            f"{entry.agent:21}{entry.route:9}{stage_cell(entry):16}"
            f"{quality_cell(entry, repo):18}{entry.value_line['stage']:11}"
            f"{drift_cell(entry, repo)}"
        )
    lines.append("")
    lines.append(f"{'agent':21}{'cost last month':20}value claim")
    for entry in entries:
        lines.append(
            f"{entry.agent:21}{cost_cell(entry):20}{entry.value_line['claim']}"
        )
    return lines
