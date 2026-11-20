# Chapter 5: Who Runs the Show

Companion code for Chapter 5 of *Agentic AI Engineering*, *Who Runs the Show: Orchestration Patterns and Model Routing*.

The chapter is about who holds the control flow, your code or the model, and what follows from that choice. The code implements each pattern against the real OpenAI Agents SDK: a code-led workflow, a bounded agent run with a defined result for every ending, checkpointed recovery, a reflection loop with a cap, handoffs and a function tool, a classifier router with an escalation route, a model registry and a canary split, plan validation, parallel specialists, approval that pauses and resumes a run, and a three-layer alert triage system that uses all of it.

The tests, the walkthrough notebook, and the `--scripted` mode of the examples need no API key. The SDK runner, the tools, the handoffs, the approval flow, and the run state are all real. Only the model's replies are scripted. Without the flag, the examples call a real model and need `OPENAI_API_KEY`.

## Setup

Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`openai-agents` is pinned to 0.24.0. Everything else the code stores goes into SQLite files, so no database server is needed.

## Run and verify

Run every command from this folder.

| Command | What it exercises | What you should see |
| --- | --- | --- |
| `python -m pytest -q` | The test suite | 34 tests passing |
| `python -m examples.invoice --scripted` | The code-led invoice workflow | One invoice posted, one sent to review |
| `python -m examples.crash_and_resume` | Checkpoints and idempotency keys | A resumed run with one hold on file, not two |
| `python -m examples.router_report` | The router's scores on 24 labeled requests, from decisions recorded from the real router | Precision and recall by category, and the threshold table printed in the chapter |
| `python -m examples.approval_roundtrip --scripted` | A run paused for approval and resumed from a database file | `awaiting_approval`, then `closed` with one payment released |
| `python -m examples.triage_day --scripted` | Four alerts through the three layers | Four different routes, three of them ending at a person |
| `python -m examples.triage_costs` | The cost arithmetic from the chapter | The six lines printed in the chapter |
| `python -m examples.invoice` | The invoice workflow with a real model. Needs `OPENAI_API_KEY` | The same two outcomes |
| `python -m examples.router_report --live` | The real router on the labeled sample. Needs `OPENAI_API_KEY` | A report with your model's own scores |
| `python -m examples.approval_roundtrip` | The approval round trip with a real model. Needs `OPENAI_API_KEY` | A pause, then a release after approval |
| `python -m examples.triage_day` | The pyramid with real models. Needs `OPENAI_API_KEY` | The first alert cleared, the second investigated and handed to an analyst, the third sent to a person to confirm although the model recommends clearing it |

The `outputs/` folder holds what every command printed when the chapter was written, scripted and live. A live model words its replies differently on every run, and its verdicts can differ from the scripted ones, so expect the same policy behavior and different details. One difference is deliberate: the scripted reply for the fourth alert cites a record that does not exist, to show the evidence check sending it to a person. A live model cites real records, so that alert is cleared.

`Chapter_5_Learning_Walkthrough.ipynb` runs the chapter's ideas in order. `python scripts/build_notebook.py` rebuilds and executes it.

## Where things are

| Path | What it holds | Chapter section |
| --- | --- | --- |
| `chapter5/models.py` | The model registry and the two reasoning settings. The only place model names appear | Pinning model versions and settings |
| `chapter5/invoices.py`, `examples/invoice.py` | A code-led workflow with one model step and a `Decimal` threshold | Code-led and model-led control: A spectrum, not a switch |
| `chapter5/investigation.py` | The investigator agent, its read-only tools, and its typed assessment | Understanding the outcomes of an agent run, The pyramid, layer by layer |
| `chapter5/run_control.py` | `run_investigation`: caps on turns and time, a result for every ending, a stored retry count | Understanding the outcomes of an agent run |
| `chapter5/recovery.py`, `examples/crash_and_resume.py` | Checkpoints and idempotency keys | Resuming a workflow after a crash |
| `chapter5/reflection.py` | A writer, a reviewer, and a capped revision loop | Letting an agent check its own work |
| `chapter5/routing.py` | Two handoffs, a typed transfer reason, an input filter, and a fee function tool | Choosing between agents as tools and handoffs |
| `chapter5/router.py` | The classifier router and its dispatch function | Building a router with an escalation option |
| `chapter5/router_eval.py`, `examples/router_report.py`, `data/router_sample.json` | Confusion counts, precision and recall, and the threshold trade | Evaluating routing accuracy |
| `chapter5/canary.py` | A stable split of requests between the current and the candidate model | Testing and gradually deploying model upgrades |
| `chapter5/planning.py` | Plan validation, revision rules, and writes that need a fresh approval | Creating and validating an execution plan |
| `chapter5/fanout.py` | Three specialists run in parallel and merged in code | Running independent tasks in parallel |
| `chapter5/approvals.py`, `examples/approval_roundtrip.py` | Conditional approval, a stored paused run, resume, and the overdue rule | Pausing and resuming work for human approval |
| `chapter5/triage.py`, `examples/triage_day.py`, `data/cases.json` | The triage agent, the policy table, the evidence check, and the three-layer flow | Putting it together: The alert triage pyramid |
| `chapter5/costs.py`, `examples/triage_costs.py` | The cost arithmetic, keyed by registry role | Estimating the costs of triage and investigation |
| `examples/scripted.py` | The scripted model replies used by the tests, the notebook, and `--scripted` | |

## What is simplified

The customers, transactions, watchlist, and alerts in `data/cases.json` are invented. The investigator's tools read that file. In production they would be MCP connections to the institution's own systems.

The ledger, the review queues, the human queue, and the analysts' desk are small in-memory classes. The retry count, the checkpoints, and the pending approvals are kept in SQLite, because the chapter's point about each of them is that they survive a restart.

The labeled router sample has 24 requests. The decisions in `data/router_sample.json` were recorded from the small model in the registry on 20 November 2026, so the keyless report is a real result. It shows how the report is built. It is far too small to evaluate a router, and `--live` will give slightly different confidence values on every run.

The specialists behind the router and the handoffs have instructions and no tools, so their replies are generic. The chapter's subject there is who receives the request, not what the specialist does with it. The sanctions screener in `chapter5/fanout.py` checks names against the sample watchlist in `data/cases.json`.

The evidence check in `chapter5/triage.py` confirms that every record a verdict cites exists in the alert. It does not confirm that the record supports the conclusion. That takes the evaluation methods of Chapter 7 and a person.

The prices in `chapter5/costs.py` are one provider's published standard rates on the date in the file, and the token counts are assumptions stated in the chapter. Replace both with your own before you rely on the result.

The model names in `chapter5/models.py` are the ones the provider published when the chapter was finalized. Change them there, and nowhere else, when the lineup moves.
