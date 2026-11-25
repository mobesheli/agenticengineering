"""Build Chapter_11_Learning_Walkthrough.ipynb from the chapter's examples.

    python scripts/build_notebook.py

The notebook follows the chapter through the agent's first year. The one cell
that needs a model drives the SDK runner through its scripted test model, so the
whole notebook runs without an API key and prints what the chapter prints.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_11_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


def run(example: str) -> nbf.NotebookNode:
    return code(f"!{{sys.executable}} -m examples.{example}")


STEPS = [
    (
        "1. Day 2, day 31, day 97: the drift view",
        (
            "Five signals, one decision. A configuration that is not the approved"
            " bundle holds and opens a candidate release, even when the results"
            " improved."
        ),
        "drift_view",
    ),
    (
        "2. Day 140 and day 175: a promotion case, twice",
        (
            "The first case fails on the one number nobody had measured: whether"
            " the reviewers still catch errors. The ceiling answers alone, and the"
            " drop rule needs no signature."
        ),
        "promotion",
    ),
    (
        "3. A spending mandate, and what revoking it leaves behind",
        (
            "Revocation stops the next order. It does not undo the ones already"
            " placed."
        ),
        "mandate_demo",
    ),
    (
        "4. Day 180: the memory hygiene pass",
        (
            "Expire, supersede, merge, verify, scored before and after. The merge is"
            " accepted on checks that do not depend on the model's own confidence."
        ),
        "hygiene",
    ),
    (
        "5. Lineage: a poisoned source and an erasure request",
        (
            "One walk answers both questions: what did this source produce, and"
            " where does every copy live."
        ),
        "lineage_demo",
    ),
    (
        "6. Day 240: fifteen agents",
        (
            "The listing check, the reconciliation with two vendor registries, and a"
            " contract change that only registered consumers were protected from."
        ),
        "fleet_demo",
    ),
    (
        "7. Day 300 onward: the agent proposes, the gate decides",
        "Three proposed fixes and two stop drills on two clocks.",
        "improvement",
    ),
    (
        "8. Retiring an agent",
        (
            "The script refuses while a credential is live, then completes and"
            " writes the record."
        ),
        "retirement",
    ),
    (
        "9. Day 365: one year on one board",
        "The rung by day, the drift record, and the ten events of the year.",
        "year_board",
    ),
]

cells = [
    md(
        """
# Chapter 11: Operating, Evolving, and Retiring Agents

This notebook mirrors the chapter. Run the cells in order, from the `Chapter11`
folder. Nothing here needs an API key. The policy code is plain Python over the
files in `data/`. The memory consolidator is a real SDK agent with a structured
output, driven here by the SDK's scripted test model.

All plant, fleet, and model data is synthetic. Pinned version: openai-agents 0.24.0.
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
]
for title, text, example in STEPS:
    cells += [md(f"## {title}\n\n{text}"), run(example)]
cells += [
    md(
        """
## 10. Try it yourself

Change one number and rerun a step. Raise `planted_check_catch_rate` in
`data/evidence.yaml`, move a band in `data/readings.yaml`, or delete a consumer
from `data/fleet.yaml` and watch the contract check stop protecting it.
"""
    ),
    code(
        """
from chapter11.autonomy import promotion_gaps
from chapter11.settings import load

rule = load("ladder")["rung_1_to_2"]
evidence = {**load("evidence")["day_140"]["evidence"]}
print(promotion_gaps(evidence, rule, target=2, ceiling=3))
evidence["planted_check_catch_rate"] = 0.95
print(promotion_gaps(evidence, rule, target=2, ceiling=3))
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
