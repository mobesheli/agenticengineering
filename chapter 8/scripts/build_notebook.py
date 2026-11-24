"""Build Chapter_8_Learning_Walkthrough.ipynb from the chapter's runnable modules.

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
OUT = ROOT / "Chapter_8_Learning_Walkthrough.ipynb"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Chapter 8: Securing Agents With Guardrails and Governance

This notebook mirrors the chapter. Run the cells in order, from the `Chapter08`
folder. Nothing here needs an API key. The SDK runner, the tools, the guardrail,
the approval pause, the policy, and the record store are real. Only the model's
replies are scripted, which makes every result the same on every run and lets us
script a model that does what an attacker wants.

Every patient record is synthetic.

Pinned version: openai-agents 0.24.0.
"""
    ),
    code(
        """
import sys
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from agents import set_tracing_disabled

set_tracing_disabled(True)
print("openai-agents", version("openai-agents"))
"""
    ),
    md(
        """
## 1. The Rule of Two

An agent working on its own may hold any two of three properties: untrusted
input, sensitive access, and the ability to change state. The reconciliation agent
needs all three, so it runs as two sessions.
"""
    ),
    code(
        """
from examples import rule_of_two

rule_of_two.main()
"""
    ),
    md(
        """
## 2. The catalog and the guardrail that enforces it

The catalog is a file. The guardrail reads it on every tool call and trusts only
the session your application created at launch.
"""
    ),
    code(
        """
from chapter8.catalog import load_catalog

catalog = load_catalog()
for agent, tools in catalog.agents.items():
    print(agent, "->", ", ".join(tools))
print(catalog.tools["write_reconciliation"])
"""
    ),
    code(
        """
from examples import guardrail_demo

await guardrail_demo.run()
"""
    ),
    md(
        """
## 3. Assume the model loses

The patient in these runs has a discharge note whose last paragraph is addressed
to the AI assistant. The scripted readers do what it says. Watch what the code
around them does.
"""
    ),
    code(
        """
from chapter8.records import load_patient

print(load_patient("patient-hostile-note").notes[0].text)
"""
    ),
    code(
        """
from examples import attack

await attack.run()
"""
    ),
    md(
        """
## 4. An approval bound to one action, one person, and a period of time
"""
    ),
    code(
        """
from chapter8.approvals import action_hash

first = {"patient_id": "pt-1001", "changes": [{"action": "add", "target": "x"}]}
same = {"changes": [{"target": "x", "action": "add"}], "patient_id": "pt-1001"}
edited = {"patient_id": "pt-1001", "changes": [{"action": "add", "target": "y"}]}
tool = "write_reconciliation"
print(action_hash(tool, first, "pt-1001")[:16], "original")
print(action_hash(tool, same, "pt-1001")[:16], "same action, keys reordered")
print(action_hash(tool, edited, "pt-1001")[:16], "one target edited")
"""
    ),
    md(
        """
## 5. Policy with a budget and a clock
"""
    ),
    code(
        """
from examples import policy_demo

await policy_demo.run()
"""
    ),
    md(
        """
## 6. The whole split session: read, review, sign, write
"""
    ),
    code(
        """
from examples import reconcile

harness = await reconcile.run(live=False)
"""
    ),
    code(
        """
patient = harness.store._patients["pt-1001"]
for medication in patient.medications:
    print(f"{medication.name:<22}{medication.status}")
print(patient.flags)
"""
    ),
    md(
        """
## 7. The approval linter
"""
    ),
    code(
        """
from examples import linter_demo

linter_demo.main()
"""
    ),
    md(
        """
## 8. Decision records, the chain, and the signed checkpoint
"""
    ),
    code(
        """
for record in harness.log.records():
    print(record.decision_id, record.kind, record.rule, record.business_ref)
mark = harness.notary.checkpoint(harness.log)
print(harness.notary.verify(harness.log.records(), mark))
"""
    ),
    code(
        """
from examples import audit_demo

await audit_demo.run()
"""
    ),
    md(
        """
## 9. Redaction before export, and the canary test

This cell turns tracing on with two exporters of our own, one raw and one
redacting. Nothing is sent to a trace backend.
"""
    ),
    code(
        """
set_tracing_disabled(False)
from chapter8.redaction import find_canaries
from examples import redaction_demo

destinations = await redaction_demo.run()
for name, payload in destinations.items():
    found = find_canaries(payload, redaction_demo.CANARIES)
    print(f"{name:<29}{len(found)} of {len(redaction_demo.CANARIES)} canaries")
set_tracing_disabled(True)
"""
    ),
    md(
        """
## 10. The emergency stop, drilled
"""
    ),
    code(
        """
from examples import stop_drill

await stop_drill.run()
"""
    ),
    md(
        """
## 11. The audit event the record server writes, in the hospital's format
"""
    ),
    code(
        """
import json

print(json.dumps(harness.store.audit[0], indent=2))
"""
    ),
    md(
        """
## Where to go next

`python -m examples.reconcile` runs the split session against live models, and
`python -m examples.live_check` repeats both phases on the clean and the hostile
record. Both need `OPENAI_API_KEY`. The model names are in `chapter8/settings.py`.
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
