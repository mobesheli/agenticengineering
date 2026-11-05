"""Build Chapter_3_Learning_Walkthrough.ipynb from the chapter's runnable modules.

    python scripts/build_notebook.py

The notebook follows the chapter section by section. Every cell that needs a model
drives the SDK runner through its scripted test model, so the whole notebook runs
without an API key. Cells use top-level await, which Jupyter supports natively.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_3_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Chapter 3: Giving Agents Hands

This notebook mirrors the chapter. Run the cells in order. Nothing here needs an
API key: every cell that involves a model drives the real SDK runner through its
scripted test model, which is also how the chapter's three failure drills were
captured. Pinned versions: openai-agents 0.24.0, mcp 2.3.0.
"""
    ),
    code(
        """
from importlib.metadata import version
print("openai-agents", version("openai-agents"), "| mcp", version("mcp"))
"""
    ),
    md(
        """
## Designing tools the model can actually use

Three intent-shaped ERP tools. Look at the model-facing schemas: the
`idempotency_key` is nowhere in them, because it travels in the run context.
"""
    ),
    code("from examples import intent_tools\nintent_tools.main()"),
    md(
        """
## Engineering the side-effect boundary

### Values the model must not control travel in the run context
"""
    ),
    code("from examples import run_context\nawait run_context.main()"),
    md(
        """
### Drill 1: retry after a lost response

The orchestration layer derives a key, the first response is lost, the retry
reuses the key, and the store ends up with exactly one refund.
"""
    ),
    code("from drills import retry_after_timeout\nawait retry_after_timeout.main()"),
    md("### Preview and execute, bound by a content hash"),
    code("from examples import preview_execute\nawait preview_execute.main()"),
    md(
        """
### Drill 2: a rejected approval

`execute_refund` is gated by a policy function. The run stops with one
interruption, a scripted reviewer says no, and the tool never runs.
"""
    ),
    code("from drills import reject_approval\nawait reject_approval.main()"),
    md("### Resuming a parked run from a serialized state, in another process"),
    code("from examples import resume_from_string\nawait resume_from_string.main()"),
    md(
        """
## Plugging in with the Model Context Protocol

### Drill 3: the server is not there

Nothing is listening on port 8765, so the connection fails fast, before any
model call, with an error that names the server.
"""
    ),
    code("from drills import unavailable_mcp_server\nawait unavailable_mcp_server.main()"),
    md(
        """
### Connecting to the finance evidence server

Start the server in a terminal first:

```
python -m mcp_servers.finance_evidence_server
```

Then run the next cell. The tool list is fetched when the run starts, inside the
`async with` block, and a run outside the block fails with `Server not initialized`.
"""
    ),
    code("from examples import mcp_connect\nawait mcp_connect.main()"),
    md(
        """
## Building a financial services audit-prep agent

The complete flow: reads from the data and policy servers, draft artifacts written
under idempotency keys, one interruption at `publish_evidence_bundle`, approval,
resume, and a tool-call journal row for every call with the principal, the
argument hash, and the policy version.
"""
    ),
    code("from audit_prep import main as audit_main\nawait audit_main.main()"),
    md(
        """
## Run-and-verify

Table 3.1 in the chapter lists what each command should show. The test suite
covers the same ground:

```
pytest -q
```
"""
    ),
]

nb = nbf.v4.new_notebook()
nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
}
nbf.write(nb, OUT)
print("wrote", OUT)
