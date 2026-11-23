"""Build Chapter_7_Learning_Walkthrough.ipynb from the chapter's runnable modules.

    python scripts/build_notebook.py

The notebook follows the chapter section by section. Every cell that needs a model
drives the SDK runner through its scripted test model, so the whole notebook runs
without an API key.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_7_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Chapter 7: Does It Actually Work?

This notebook mirrors the chapter. Run the cells in order, from the `Chapter07`
folder. Nothing here needs an API key. The SDK runner, the reviewer's tools, the
graders, the gate, and the evidence pack are all real. Only the model's replies
are scripted, which also makes every result below the same on every run.

All the numbers are illustrative. They show what the evidence looks like.

Pinned version: openai-agents 0.24.0.
"""
    ),
    code(
        """
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from chapter7.graders import grade_trial, has_repeated_call
from chapter7.runner import ToolCall, run_suite
from chapter7.tasks import load_tasks, task_by_id
from examples import (
    evidence_pack,
    gate_demo,
    judge_calibration,
    one_task,
    reliability,
    show_task,
    suite_run,
)
from examples.scripted import scripted_reviewer

print("openai-agents", version("openai-agents"))
"""
    ),
    md(
        """
## Understanding why unit tests are not enough for agents

One success rate, read two ways. Pass@k asks whether at least one of k trials
succeeded. Pass^k asks whether all of them did. The second table is the same
arithmetic for steps in a chain. Both tables assume independence, which real
agents do not have, so they are a warning and not an estimate.
"""
    ),
    code("reliability.main()"),
    md(
        """
## Building golden task suites and checking trajectories

A task has a success criterion, a starting state, a reference solution, and an
expected outcome. The second task below is the first one with a sentence added
to the entry's description, addressed to the agent. Its expected outcome does
not change.
"""
    ),
    code(
        """
show_task.main()

tasks = load_tasks()
print()
golden = sum(t.kind == "golden" for t in tasks)
print(len(tasks), "tasks:", golden, "golden,", len(tasks) - golden, "abuse")
"""
    ),
    md(
        """
One task, four trials. The runner provisions a fresh environment for each trial,
runs the reviewer through the SDK, and keeps the transcript and the final state.
"""
    ),
    code("grades = await one_task.main(scripted_run=True)"),
    md(
        """
A trajectory check sees what an outcome check cannot. In the task below, one
trial records the right verdict before it reads the policy.
"""
    ),
    code(
        """
task = task_by_id("je-clarify-03")
trials = await run_suite(scripted_reviewer("baseline"), [task], k=4)
for trial in trials:
    grade = grade_trial(task, trial)
    steps = " > ".join(call.name for call in trial.transcript.tool_calls)
    print(trial.index + 1, trial.final_state["verdict"], grade.failures or "pass")
    print("  ", steps)
"""
    ),
    md(
        """
The loop check counts identical successful calls and skips failed ones, so a
retry after a timeout is not punished.
"""
    ),
    code(
        """
read = {"name": "get_supporting_documents", "arguments": '{"entry_id": "JE-2001"}'}
retry = [ToolCall(**read, failed=True), ToolCall(**read)]
loop = [ToolCall(**read), ToolCall(**read), ToolCall(**read)]
print("retry after a timeout is a loop:", has_repeated_call(retry))
print("three identical successful calls is a loop:", has_repeated_call(loop))
"""
    ),
    md(
        """
## Grading at scale with a model judge

The judge is measured against reference labels before anyone trusts it. The
verdicts below were recorded, and the labels are synthetic, so the result is
illustrative. `python -m examples.judge_calibration --live` runs the real judge.
"""
    ),
    code("calibration = await judge_calibration.main()"),
    md(
        """
## Testing how the agent behaves under attack

Abuse tasks live in the same dataset and run through the same code. Each one is
an entry that should be flagged, carrying an attack that tries to prevent that.
"""
    ),
    code(
        """
for task in load_tasks():
    if task.kind == "abuse":
        print(f"{task.task_id:16} {', '.join(task.tags)}")
"""
    ),
    md(
        """
## Implementing regression gates to prevent unreliable deployments

A full run of both suites at four trials each, and then the gate applied to
three candidate versions of the reviewer. The last three lines judge one drop
two ways: as two separate runs, and paired by task.
"""
    ),
    code(
        """
run = await suite_run.main(scripted_run=True)
print()
verdicts = await gate_demo.main()
"""
    ),
    md(
        """
## Real-world pattern: An evaluation harness for a journal entry reviewer

The evidence pack maps each output of the harness to a question a reviewer asks.
"""
    ),
    code("written = await evidence_pack.main()"),
    md(
        """
## Running against a live model

Set `OPENAI_API_KEY` and run the examples without `--scripted`:

    python -m examples.one_task
    python -m examples.suite_run
    python -m examples.suite_run --judge
    python -m examples.judge_calibration --live

A full live run is 128 reviews, plus 128 judge calls with `--judge`. The suite
example prints the cost of the run.
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
