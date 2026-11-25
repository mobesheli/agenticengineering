"""Build Chapter_9_Learning_Walkthrough.ipynb from the chapter's runnable modules.

    python scripts/build_notebook.py

The notebook follows the chapter section by section. Every cell that needs a model
drives the SDK runner through its scripted test model, so the whole notebook runs
without an API key and prints the same figures as the chapter.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_9_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


def run(example: str) -> nbf.NotebookNode:
    return code(f"!{{sys.executable}} -m examples.{example}")


cells = [
    md(
        """
# Chapter 9: Measuring Agent Observability, Cost, and ROI

This notebook mirrors the chapter. Run the cells in order, from the `Chapter09`
folder. Nothing here needs an API key. The SDK runner, the tools, the meter, the
run budget, the guardrail, and the ledger are real. Only the model's replies and
the token counts it reports are scripted, which makes every dollar figure the same
on every run.

All plant data is synthetic. Prices come from `data/price-card.yaml`.

Pinned version: openai-agents 0.24.0.
"""
    ),
    code(
        """
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
print("openai-agents", version("openai-agents"))
"""
    ),
    md(
        "## 1. What one approved work order costs\n\nTable 9.1, computed from the month's ledger."
    ),
    run("unit_cost"),
    md(
        """
## 2. The price card and the meter

Every cost comes from one versioned file. The meter splits a usage report into five
lines. Reasoning tokens are part of the output count, so they are priced once and
shown on their own line.
"""
    ),
    code(
        """
from dataclasses import asdict

from chapter9.meter import price_usage, usage_of
from chapter9.pricecard import UnknownPrice, load_price_card

card = load_price_card()
print("price card", card.version, card.rates("gpt-6.2-sol"))
cost = price_usage(
    usage_of(10_000, 2_000, cached=6_000, written=1_000, reasoning=1_200),
    card.rates("gpt-6.2-sol"),
)
for line, usd in asdict(cost).items():
    print(f"  {line:<15}${usd:.4f}")
print(f"  {'total':<15}${cost.total:.4f}")
try:
    card.rates("gpt-7-preview")
except UnknownPrice as error:
    print(error)
"""
    ),
    md(
        """
## 3. One run, span by span

The same work twice: every step on the frontier model with nothing cached, then
with a cached prefix and a model chosen for each step. Look for the repeated call.
"""
    ),
    run("one_run"),
    md(
        "## 4. A call across the border\n\nYour own record of a call to a supplier's agent."
    ),
    run("border"),
    md("## 5. The anatomy of one turn\n\nFigure 9.3 is drawn from this table."),
    run("one_turn"),
    md(
        """
## 6. Why the bill rose, and whether the ledger matches the invoice

Runs, tokens per run, and price per token, then the reconciliation, then the
production metrics for the two months.
"""
    ),
    run("why_bill_rose"),
    md(
        """
## 7. The run budget

A model that keeps asking the same question. The guardrail refuses the repeats, and
the budget stops the run before the call that would exceed it.
"""
    ),
    run("budget_stop"),
    md(
        """
Try it yourself: give the run a larger budget and a smaller number of model calls,
and see which limit stops it.
"""
    ),
    code(
        """
from chapter9.budget import BudgetExceeded, RunBudget
from chapter9.planner import RunContext, plan_work_order
from examples.common import frontier_agents, start
from examples.scripted import MACHINE, TAGS, stuck_run

card, ledger = start()
budget = RunBudget(limit_usd=5.00, model_calls=4, tool_calls=8)
agents = frontier_agents(*stuck_run(), card, budget, guarded=True)
try:
    await plan_work_order(MACHINE, agents, RunContext(budget), TAGS)
except BudgetExceeded as stop:
    print("stopped:", stop)
"""
    ),
    md(
        "## 8. Where the model spend goes\n\nBy step and by model, before and after."
    ),
    run("token_share"),
    md(
        """
## 9. Cheaper is not the same as better value

Three configurations compared on cost per approved order. Figure 9.4 is drawn from
this table.
"""
    ),
    run("frontier"),
    md(
        """
## 10. The finance view

Cost per approved work order by plant, as it first looks and then like for like,
with an interval on every rate and a verdict that uses both ends of it.
"""
    ),
    run("by_plant"),
    md(
        """
## 11. Live models

`python -m examples.live_check` runs the planner against live models and checks
that the provider's usage report has the fields the meter prices. It needs
`OPENAI_API_KEY` and costs a few cents, so it is not run here.
"""
    ),
]

notebook = nbf.v4.new_notebook(cells=cells)
notebook.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
NotebookClient(
    notebook,
    timeout=120,
    kernel_name="python3",
    resources={"metadata": {"path": str(ROOT)}},
).execute()
nbf.write(notebook, OUT)
errors = [
    o
    for c in notebook.cells
    if c.cell_type == "code"
    for o in c.get("outputs", [])
    if o.get("output_type") == "error"
]
print(f"wrote {OUT.name}: {len(notebook.cells)} cells, {len(errors)} errors")
