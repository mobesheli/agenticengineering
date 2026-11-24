# Chapter 10: Deploying Agents

Companion code for Chapter 10 of *Agentic AI Engineering*, *Deploying Agents: Patterns and Infrastructure*.

The chapter takes one agent, a maintenance planner for a manufacturer with four plants, from a prototype to a production service, and then builds one governed way to deploy every agent after it. This folder holds the pieces: a worker that pauses a run at an approval and resumes it in another process, tool contracts enforced before every call, a release bundle, a release pipeline with an evaluation gate, six kill switches with a drill, and a register with a listing check, an intake, and a dashboard.

The tests, the walkthrough notebook, and the examples need no API key. The SDK runner, the tools, the tool guardrails, the approval pause, the state store, the pipeline, and the register are all real. Only the model's replies are scripted, which also makes the output the same on every run. One example can also call a real model and needs `OPENAI_API_KEY` for that.

## Setup

Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`openai-agents` is pinned to 0.24.0. The worker stores sessions and parked runs in a SQLite file through SQLAlchemy, so nothing else needs installing. SQLite allows one writer, so the store uses one connection at a time. Point the same code at a server database in production.

## Run and verify

Run every command from this folder.

| Command | What it exercises | What you should see |
| --- | --- | --- |
| `python -m pytest -q` | The test suite | 60 tests passing |
| `python -m examples.pause_resume --scripted` | A run parked at an approval and resumed by a second worker | One work order after approval, a repeated approval refused, a stale approval voided |
| `python -m examples.contract_demo` | A tool contract refusing an operation, then the server refusing it | A policy denial, then a server refusal |
| `python -m examples.bundle_show` | The release bundle, its digest, and its pointers | The bundle, one digest, and "all match" |
| `python -m examples.pipeline_run` | Two attempts at one release, in each gate mode | A regression that only block mode stops, a secret that every mode stops, and a passing run |
| `python -m chapter10.pipeline --repo template-repository --mode block` | The pipeline as a pipeline stage would run it | Four stages and exit code 0 |
| `python -m examples.rollout_demo` | A canary at one plant, a rollback, and what the rollback leaves | Three things the pointer did not undo |
| `python -m examples.switch_drill` | Each of the six switches pulled on a copy of staging | Six lines that say "stopped" |
| `python -m examples.listing_demo` | Unregistered agents found, and a listing refused twice and then accepted | Three findings and three attempts |
| `python -m examples.intake_demo` | Three proposals through intake | Reuse, buy, and one build with a starter project |
| `python -m examples.buy_route` | A bought agent's gap sheet at two tiers | No blocking gaps at its own tier, two at the highest |
| `python -m examples.board` | The dashboard, read from the register and its records | Four rows, a cost table, and the drift signal counts |
| `python -m examples.pause_resume` | The pause and resume with a real model. Needs `OPENAI_API_KEY` | The same three cases, in the model's own words |

The `outputs/` folder holds what every command printed when the chapter was written, including one live run in `pause_resume_live.txt`. `tests/test_outputs.py` checks that each scripted example still prints exactly what is stored. A live model words its messages differently on every run.

`Chapter_10_Learning_Walkthrough.ipynb` runs the chapter's ideas in order. `python scripts/build_notebook.py` rebuilds and executes it. `python scripts/build_data.py` regenerates the evaluation results, the register, and the evidence records.

## Where things are

| Path | What it holds | Chapter section |
| --- | --- | --- |
| `chapter10/worker.py` | `run_turn` and `resume`, and the table of parked runs with its atomic claim | Pausing runs without holding workers open |
| `chapter10/planner.py` | The agent being deployed and its tools. One tool needs a human approval | Pausing runs without holding workers open |
| `chapter10/contracts.py`, `template-repository/contracts/` | Tool contracts and the guardrail that enforces them before a call | Enforcing tool contracts before every call |
| `chapter10/platform.py` | A small stand-in for the gateway, the identity directory, the endpoints, the register, and the data catalog | Implementing six ways to stop an agent |
| `chapter10/bundle.py`, `template-repository/bundle.yaml` | The release bundle, its digest, and the check that its pointers match their files | Versioning the complete agent bundle |
| `chapter10/models.py` | Model settings and prices. The model names themselves live in the bundle | Pinning the model |
| `chapter10/gate.py` | The result every suite reports, the paired decision rule, and the three gate modes | Enforcing the evaluation gate in CI/CD |
| `chapter10/pipeline.py`, `template-repository/pipeline.yaml` | The release pipeline: secret scan, bundle pointers, contract rules, the gate, and the release record | Enforcing the evaluation gate in CI/CD |
| `chapter10/release.py` | The canary, the rollback, and what a rollback leaves behind | Rolling out and rolling back safely |
| `chapter10/switches.py` | The six switches and the drill | Implementing six ways to stop an agent |
| `chapter10/register.py`, `data/register/` | Register entries, the listing check, and the search for unregistered agents | Checking evidence before listing agents |
| `chapter10/intake.py` | The reuse, buy, or build recommendation | Screening proposals before development |
| `chapter10/adapter.py` | The adapter that brings a team's own evaluation suite to the gate | Choosing an adoption route |
| `chapter10/gaps.py` | The gap sheet for a bought agent | Choosing an adoption route |
| `chapter10/board.py` | The dashboard | Real-world pattern |
| `examples/scripted.py` | The scripted model replies used by the tests, the notebook, and `--scripted` | |
| `template-repository/` | What an agent's own repository looks like on the governed path | Packaging an agent |

## What is simplified

Everything is invented: the manufacturer, the plants, the equipment, the agents, the evaluation results, the costs, and the evidence records. The numbers show what the artifacts look like. They are not measurements.

`chapter10/platform.py` is a stand-in. In production, the gateway, the identity directory, the endpoints, and the data catalog are separate services with their own interfaces. Here they are fields on one object, so that a drill can pull a switch and a probe can show what stopped. The drill reports whether each switch worked. A real drill also times it.

The digests in `template-repository/bundle.yaml` are shortened to twelve characters so that the file can be printed. Real digests are 64 characters. The prompt's hash is real and is checked by the pipeline.

The evaluation results in `template-repository/evals/` are files, not runs. The golden suite that would produce them is the subject of Chapter 7. The gate here reads results in one common form, applies the same paired rule as Chapter 7, and decides.

The release record is a JSON file with the hash of the evaluation report. In production, the pipeline signs that record with its own identity, as it signs the image, so that nobody can write one by hand.

The template repository shows the layout: the bundle, the contracts, the prompt, the policy file, the pipeline stage, a workflow for a Git host, and a Dockerfile that shows what is copied into the image and what is not. The Dockerfile is not built by the tests.

The model names in `template-repository/bundle.yaml` are the ones the provider published when the chapter was finalized, and the prices in `chapter10/models.py` are that provider's standard rates on the date in the file. Change the names in the bundle, and nowhere else, when the lineup moves.
