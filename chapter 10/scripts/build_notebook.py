"""Build Chapter_10_Learning_Walkthrough.ipynb from the chapter's runnable modules.

    python scripts/build_notebook.py

The notebook follows the chapter section by section. The one cell that needs a
model drives the SDK runner through its scripted test model, so the whole notebook
runs without an API key.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_10_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Chapter 10: Deploying Agents

This notebook mirrors the chapter. Run the cells in order, from the `Chapter10`
folder. Nothing here needs an API key. The SDK runner, the tools, the approval
pause, the state store, the pipeline, and the register are real. Only the model's
replies are scripted, which also makes every result below the same on every run.

All the agents, figures, and records are illustrative.

Pinned version: openai-agents 0.24.0.
"""
    ),
    code(
        """
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from examples import (
    board,
    bundle_show,
    buy_route,
    contract_demo,
    intake_demo,
    listing_demo,
    pause_resume,
    pipeline_run,
    rollout_demo,
    switch_drill,
)

print("openai-agents", version("openai-agents"))
"""
    ),
    md(
        """
## Choosing where an agent runs

A run stops at an approval and is parked in a table the agent cannot write to.
A second worker, with no memory of the first, resumes it after the planner
approves. The same approval cannot be used twice, and an approval given under
an old release is void.
"""
    ),
    code("lines = await pause_resume.main(scripted_run=True)"),
    md(
        """
## Packaging an agent: What goes in and stays out

A tool contract names what a server may be asked to do. The check runs before
the call, and the server makes its own decision afterward. The second half of
the output is what happens when somebody loosens the contract by mistake.
"""
    ),
    code("lines = await contract_demo.main()"),
    md(
        """
## Building a reproducible release bundle and evaluation gate

The bundle is one file that names everything that changes how the agent
behaves. The pipeline checks that every pointer in it still matches the file it
names, and one digest names the release.
"""
    ),
    code("lines = bundle_show.main()"),
    md(
        """
The pipeline runs two attempts at the same release. The first attempt regressed,
and only block mode stops it. A committed key stops the pipeline in every mode,
because mandatory checks are never part of the gate's rollout.
"""
    ),
    code("lines = pipeline_run.main()"),
    md(
        """
A canary moves one plant to the new bundle, and a rollback moves it back. The
last three lines are what the rollback did not undo.
"""
    ),
    code("lines = await rollout_demo.main()"),
    md(
        """
## Stopping agents safely in production

Six switches, each pulled on its own copy of staging, and then a probe that tries
the thing that should have stopped.
"""
    ),
    code("lines = switch_drill.main()"),
    md(
        """
## Scaling the platform with one path, register, and dashboard

The register is compared with the systems an agent cannot avoid, and then the
maintenance planner earns its listing on the third attempt.
"""
    ),
    code("lines = listing_demo.main()"),
    md("Three proposals go through intake. Only one becomes a build."),
    code("lines = intake_demo.main()"),
    md(
        """
## Choosing an adoption route: Build, join, assemble, or buy

A bought agent's gap sheet, read at its own tier and then at the highest tier
with a contract term where a control should be.
"""
    ),
    code("lines = buy_route.main()"),
    md(
        """
## Real-world pattern: Reviewing four agents on one dashboard

One row for each agent, read from its register entry and the records the entry
points at. The joined service's result comes through the adapter.
"""
    ),
    code("lines = board.main()"),
    md(
        """
## Running against a live model

Set `OPENAI_API_KEY` and run the pause and resume example without `--scripted`:

    python -m examples.pause_resume

The planner then uses the model pinned in `template-repository/bundle.yaml`.
"""
    ),
]


def main() -> None:
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    NotebookClient(
        notebook, timeout=300, resources={"metadata": {"path": str(ROOT)}}
    ).execute()
    nbf.write(notebook, OUT)
    print(f"wrote {OUT.name} with {len(cells)} cells")


if __name__ == "__main__":
    main()
