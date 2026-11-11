"""Build Chapter_6_Learning_Walkthrough.ipynb from the chapter's runnable modules.

    python scripts/build_notebook.py

The notebook follows the chapter section by section. Every cell that needs a model
drives the SDK runner through its scripted test model, so the whole notebook runs
without an API key. Cells use top-level await, which Jupyter supports natively.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Chapter_6_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Chapter 6: Agents That Collaborate

This notebook mirrors the chapter. Run the cells in order, from the `Chapter06`
folder. Nothing here needs an API key. Two supplier agents run as real A2A
servers inside this process, with signed Agent Cards and task endpoints, and the
cells call them through the official A2A client. Only the model is replaced, by
the Agents SDK's scripted test model.

Pinned versions: a2a-sdk 1.3.0, openai-agents 0.24.0.
"""
    ),
    code(
        """
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
for package in ("a2a-sdk", "openai-agents"):
    print(f"{package:14} {version(package)}")
"""
    ),
    md(
        """
## Diplomacy has a protocol: Inside A2A

### Discovering a peer with the Agent Card

Build NordBolt's card, sign it, verify the signature, then change one skill
description and verify again. The changed card must be refused.
"""
    ),
    code(
        """
from examples import show_card

show_card.main()
"""
    ),
    md(
        """
### Opening a task

The task states, as they are written on the wire. Four are terminal. Two park a
task until the caller supplies input or authentication.
"""
    ),
    code(
        """
from a2a.types import TaskState

for name in TaskState.keys():
    print(name)
"""
    ),
    md(
        """
## Opening the embassy: Exposing your agent over A2A

### Deciding what the card advertises

The agent behind the card is an ordinary Agents SDK agent. Its tools are private.
Its output type is the public contract.
"""
    ),
    code(
        """
from chapter6.agent import build_quote_agent
from chapter6.contracts import FastenerQuote

agent = build_quote_agent()
print("agent  :", agent.name)
print("tools  :", ", ".join(tool.name for tool in agent.tools))
print("output :", agent.output_type.__name__)
print("fields :", ", ".join(FastenerQuote.model_fields))
"""
    ),
    md(
        """
### Bridging the run loop to the task lifecycle, and serving the agent

One round trip: registry lookup, card verification, a quote task through
NordBolt's border control and executor, and a validated artifact. The last three
lines are the boundary audit record.
"""
    ),
    code(
        """
from examples import quote_roundtrip

await quote_roundtrip.main()
"""
    ),
    md(
        """
### Border control

A bill of materials with an instruction hidden in a part description. Read the
`model calls` line: the request is refused before the agent runs.
"""
    ),
    code(
        """
from drills import hostile_request

await hostile_request.main()
"""
    ),
    md(
        """
## Hiring a stranger: Consuming remote agents

### Finding a remote agent

A registry entry stores the trust relationship, of which the key is one part.
"""
    ),
    code(
        """
from chapter6.neighborhood import build_neighborhood
from chapter6.registry import CounterpartyRegistry

registry = CounterpartyRegistry()
hood = build_neighborhood(registry)
entry = registry.require("nordbolt")
trust = entry.trust
print("organization :", trust.organization)
print("card         :", trust.card_version, trust.card_fingerprint)
print("trust anchor :", trust.trust_anchor)
print("contract     :", trust.contract_reference)
print("approved by  :", trust.approved_by)
for key in trust.signing_keys:
    print(f"key          : {key.kid}, {key.not_before} to {key.not_after}")
print("wait up to   :", entry.sla_seconds, "seconds")
await hood.aclose()
"""
    ),
    md(
        """
The same server presents three cards in turn: the approved card signed with the
previous key, the approved card signed with an unknown key, and a validly signed
card whose content has changed.
"""
    ),
    code(
        """
from drills import untrusted_card

await untrusted_card.main()
"""
    ),
    md(
        """
### Calling a remote agent

A request that leaves out the drawing revision for a custom part. The supplier
parks the task and asks. The answer goes back on the same task.
"""
    ),
    code(
        """
from drills import parked_task

await parked_task.main()
"""
    ),
    md(
        """
### Handling remote agent failures

NordBolt goes offline. Three failures open its circuit breaker, the fourth call
is refused locally, and a fan-out still returns the second supplier's quote.
"""
    ),
    code(
        """
from drills import supplier_down

await supplier_down.main()
"""
    ),
    md(
        """
## Putting it together: A supply chain across three organizations

### Running a sourcing round

Fan out, compare in plain code, propose, approve one order at one price, commit,
and print the boundary audit trail. The two quote lines in the trail can appear in
either order, because the requests run in parallel.
"""
    ),
    code(
        """
from drills import sourcing_run

await sourcing_run.main()
"""
    ),
    md(
        """
The commit is retried with the same purchase order number, then attempted with
the same number and a different quantity. One order must exist at the end.
"""
    ),
    code(
        """
from drills import retry_same_message

await retry_same_message.main()
"""
    ),
    md(
        """
### The three-day silence

The webhook handler: early notifications held and released, a duplicate
acknowledged and ignored, and a wrong token refused.
"""
    ),
    code(
        """
from drills import three_day_silence

await three_day_silence.main()
"""
    ),
    md(
        """
## Self-check

The test suite covers the same behavior with assertions. Every test should pass.
"""
    ),
    code(
        """
import subprocess

done = subprocess.run(
    [sys.executable, "-m", "pytest", "-q", "--color=no"],
    capture_output=True,
    text=True,
)
print(done.stdout.strip().splitlines()[-1])
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
    print(f"wrote {OUT.name}: {len(cells)} cells, executed")


if __name__ == "__main__":
    main()
