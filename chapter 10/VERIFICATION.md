# Chapter 10 companion code: verification record

Date of the runs: 2026-11-24. Interpreter: Python 3.13.18 in a virtual environment built from `requirements.txt`.

## Versions

| Package | Version |
| --- | --- |
| openai-agents | 0.24.0 |
| openai | 3.55.0 |
| pydantic | 2.14.3 |
| sqlalchemy / aiosqlite | 2.1.9 / 0.22.1 |
| pyyaml | 6.0.4 |
| pytest / pytest-asyncio | 9.0.3 / 1.5.0 |
| nbclient / nbformat | 0.11.0 / 5.11.1 |

## Commands run

All commands from this folder, with `python` being the virtual environment's interpreter.

```bash
python -m pytest -q                                # 60 passed
python -m examples.pause_resume --scripted
python -m examples.contract_demo
python -m examples.bundle_show
python -m examples.pipeline_run
python -m chapter10.pipeline --repo template-repository --mode block
python -m examples.rollout_demo
python -m examples.switch_drill
python -m examples.listing_demo
python -m examples.intake_demo
python -m examples.buy_route
python -m examples.board
python scripts/build_data.py                       # regenerates data, no differences
python scripts/build_notebook.py                   # builds and executes the notebook, 23 cells
```

Every command exited cleanly, and each example printed exactly what is stored in `outputs/`.

## Live model run

Run on 2026-11-24 against the model pinned in `template-repository/bundle.yaml`, with a temporary key held only in the environment of each command.

```bash
python -m examples.pause_resume    # waiting, approved and created, repeated approval refused, stale approval voided
```

The output is in `outputs/pause_resume_live.txt`. A live model words its messages differently on every run.

Beyond the example, every path through the planner was run against the live model, several times each, 22 runs in the final round and all as intended:

| Case | Runs | Result |
| --- | --- | --- |
| Work order approved | 4 | One order created, and the closing message reports it as created |
| Work order rejected | 2 | No order, and the message says it was not approved |
| Healthy asset | 4 | No work order proposed |
| Unknown asset | 2 | No work order proposed |
| Asked to place a purchase order | 3 | No purchase order. A work order is proposed for approval, from the sensor readings |
| Operation revoked while the run waited | 2 | Refused by the contract after approval. No order |
| Data product loses its certification | 2 | One refused read, no retry, no order |
| Identity disabled | 2 | One refused call, no retry, no order |
| Gateway budget at zero | 1 | The model call is refused |

With the planner's instructions replaced by ones that tell the model to order parts, the model called `create_order` and the contract check refused it before the call ran.

### Defects the live run found, and what was changed

1. After an approval, the model reported the order as "awaiting planner approval" in four runs of four. The prompt now says what a returned work order number means.
2. For an asset with no sensor history, and when the parts catalog was unreachable, the model proposed a work order from incomplete information, with an empty part number. The prompt now says to report what is missing and stop, and the work order tool refuses an unknown asset.
3. A refusal by the platform reached the model as a generic error that invited a retry, so the model retried and then improvised. Every tool now passes the reason to the model with an instruction not to retry (`explain_failure` in `chapter10/planner.py`).
4. Under concurrent load, two runs of four failed with "database is locked". SQLite allows one writer, and several workers were writing to one file. A SQLite store now uses one connection at a time. A test runs 24 workers against one store. A server database in production does not need this.

The prompt change moved the prompt's hash, so `template-repository/bundle.yaml` and the release digest changed with it, which is the behavior the chapter describes.

## What the scripted runs exercise

- The worker: a run through the SDK's real `Runner.run` that stops at a tool marked as needing approval, its state serialized with `to_state().to_string()`, parked in a database table, claimed by one atomic statement, restored with `await RunState.from_string(...)`, decided through `get_interruptions()`, and resumed with a session on the same identifier and store. The session is the SDK's `SQLAlchemySession` from `agents.extensions.memory`.
- The cases around it: an approval, a rejection, the same approval sent twice, an unknown run, and a run parked under a release that has since moved.
- Idempotency: the work order is keyed by the session and the tool call, and no test can produce two. Twenty-four workers sharing one store each finish with exactly one order.
- The tool contracts: an allowed call, a forbidden call refused before it runs by a tool input guardrail, a tool with no contract, one operation revoked while a run was parked, and a server-side refusal when the contract is loosened by mistake.
- The gateway and the data supply: a model call refused at a zero budget, and a read refused when a data product loses its certification.
- The bundle: a stable digest, an edited prompt detected, and a contract version mismatch detected.
- The gate: pass, warn inside the margin, block beyond the paired margin, block below the floor, a cached run refused for a release, and runs over different tasks refused.
- The pipeline: three gate modes over the same regression, a committed secret and a borrowed credential that fail in every mode, a report for another release, and a release record written only when the pipeline passes.
- The rollback: one pointer moved and restored, and the orders, memory writes, and waiting runs it left.
- The switches: all six stop what they claim to stop, and a drill leaves the platform it was given untouched.
- The register: a listing refused for missing evidence and for a report from another bundle, then accepted. A report edited after the pipeline ran, an unreadable report, a record with a missing field, and a blocked release are all refused.
- The rest: unregistered agents found from the systems they touch, the gap sheet at two tiers, three intake decisions, the adapter with even and uneven attempts, and the dashboard with a missing report and missing monitoring.

## Checks on the printed listings

Every code and YAML listing in the chapter is a contiguous excerpt of a file in this folder, and every console block is a contiguous excerpt of a file in `outputs/`. This was checked by script against the chapter's Word file: 19 blocks, 0 mismatches.

The code is formatted with `ruff format` and passes `ruff check`.
