# Chapter 5 companion code: verification record

Date of the run: 2026-11-20. Interpreter: Python 3.13.18 in a virtual environment built from `requirements.txt`.

## Versions

| Package | Version |
| --- | --- |
| openai-agents | 0.24.0 |
| openai | 3.55.0 |
| pydantic | 2.14.3 |
| pytest / pytest-asyncio | 9.0.3 / 1.5.0 |
| nbclient / nbformat | 0.11.0 / 5.11.1 |

## Commands run

All commands from this folder, with `python` being the virtual environment's interpreter.

```bash
python -m pytest -q                                # 34 passed
python -m examples.invoice --scripted
python -m examples.crash_and_resume
python -m examples.router_report
python -m examples.approval_roundtrip --scripted
python -m examples.triage_day --scripted
python -m examples.triage_costs
python scripts/build_notebook.py                   # builds and executes the notebook, 35 cells
python -m examples.invoice                         # live model
python -m examples.router_report --live            # live model
python -m examples.approval_roundtrip              # live model
python -m examples.triage_day                      # live models
```

Every command exited cleanly. The printed results are in `outputs/`.

## What the scripted runs exercise

- The code-led workflow: a typed extraction with a `Decimal` amount, and a review threshold that is a comparison in code.
- Run control: a run that concludes, a run that reaches the turn cap, a run that reaches the time cap, a refusal, and malformed output retried once with the count stored in SQLite. The exceptions are the SDK's own `MaxTurnsExceeded`, `ModelRefusalError`, and `ModelBehaviorError`, raised by the real runner.
- Recovery: a pipeline that crashes after a side effect and before its checkpoint, then resumes from a second store object on the same database file and repeats the step under the same idempotency key.
- Reflection: a draft that is revised until the reviewer accepts it, and a loop that stops at its cap and reports that the draft did not pass.
- Handoffs: a transfer through the SDK's `transfer_to_dispute_specialist` tool with a typed reason recorded by `on_handoff`, and a fee question answered by a function tool while the intake agent keeps the conversation.
- The router: a confident decision dispatched to a specialist, and both `other` and a low-confidence decision sent to the human queue.
- Router evaluation: confusion counts, precision and recall, and the threshold report.
- The canary split: stable for a given request identifier, and close to its configured share over 20,000 identifiers.
- Plans: a plan rejected for a tool that is not allowed and for exceeding its step budget, a revision rejected for repeating a completed step, for exceeding the remaining budget, and for exceeding the replan limit, and a new writing step reported as needing approval.
- Fan-out: three specialists run through `asyncio.gather`, merged in code, with a failed specialist named in the result and treated as high risk.
- Approval: `needs_approval` as a function of the tool's arguments, a small payment released without a pause, a large payment paused through `result.interruptions`, the run serialized with `to_state().to_string()`, restored with `RunState.from_string` through a second store object, approved, and resumed. A rejection reaches the model as the tool's result and nothing is released. An unanswered request is rejected and held.
- The pyramid: each of the four sample alerts takes the route the policy gives it, an alert type missing from the policy table is never cleared by the system, a verdict that cites a record that does not exist goes to a person, and the quality sample is stable and close to its share.

## Listings

Every code listing and console block in the chapter was compared with these files, line for line and with the same indentation, using the Word file itself as the source. All 23 blocks match.

## What the live runs showed

Models: `gpt-6-luna` for the extractor, the router, triage, and the reviewer, `gpt-6.1-terra` for intake, the writer, and the fan-out specialists, `gpt-6.2-sol` for the investigator and the dispute and fraud specialists. All four registry models, including the canary, answered with both reasoning settings.

- Invoice workflow, 3 runs: both invoices extracted, the amount parsed into a `Decimal` from the model's structured output, one posted and one sent to review every time.
- Router, 6 passes over the 24 labeled requests: 20 of 24 agreed with the label on every pass. Two ambiguous requests were classified as `other` and went to a person. Two were misrouted, one with a confidence that ranged from 0.78 to above 0.90 and one between 0.96 and 0.98. In the three passes where every value was logged, 63 of 72 confidence values were 0.95 or higher and the lowest was 0.72, so the router's 0.70 threshold never fired. One pass is recorded in `data/router_sample.json` and is the table printed in the chapter.
- Dispatch, 4 requests: a balance question, a dispute, and a fraud report reached their specialists, and an unrelated request was queued for a person.
- Handoffs, 3 runs: a duplicate hotel charge was transferred to `dispute_specialist` with a typed reason carrying the transaction reference, a fee question was answered through `estimate_fees` with `intake_agent` keeping the conversation, and a policy question was transferred to `faq_agent` through the input filter.
- Run control: the investigator concluded on three alerts in 8 to 11 seconds each, typically with two model requests. With the turn cap set to 1, and separately with the time cap set to 1 second, the function returned `escalated_to_human` with "Budget spent before a conclusion."
- Reflection, 2 runs: the writer cited a record after every statement and the reviewer accepted the first draft both times. The revision path was exercised only by the scripted tests.
- Fan-out, 3 runs: three specialists ran in parallel, the screener called `screen_counterparty`, and the merged view carried record identifiers only, with high risk for the structuring alert and low risk for the supplier payment.
- Approval, 6 runs: a payment below the limit was released without a pause. A payment above it paused, and nothing was released while it waited. Approved through a second store object on the same database file, it was released. Rejected, nothing was released and the model reported the reviewer's note. Left unanswered past the deadline, it was rejected and held.
- Triage, 10 runs per alert: the supplier payment was recommended for clearing every time with confidence from 0.90 to 0.98, the structuring alert was recommended for investigation every time, and the sanctions alert was recommended for clearing every time with confidence from 0.93 to 0.99. All 40 verdicts cited only records present in the alert.
- The pyramid, 4 full runs: `alert-0001` cleared, `alert-0002` investigated with the investigator recommending escalation and citing the three transactions, `alert-0003` sent to a person to confirm in spite of the model's confidence, `alert-0004` cleared.
- Tokens on the sample data: about 340 input and 160 output for one triage pass, and about 1,400 input and 330 output for one investigation. The sample alerts are a few lines each. The chapter's cost example assumes realistic case files and is not derived from these figures.

## What the live runs changed

The first live pass found five things the scripted tests could not, and all are fixed in this code:

- Triage verdicts failed the evidence check for formatting reasons. The model copied the square brackets the case file put around each identifier, or listed the alert's own identifier as evidence. The case file now shows `identifier: content`, and the instructions ask for identifiers from the records section only.
- The investigator and the fan-out specialists wrote sentences in their evidence fields. Their instructions now ask for record identifiers, with the reasoning in the rationale or summary.
- The sanctions alert had one record, so a careful model would not clear it and the policy override was never exercised live. It now carries the customer profile and the screening note.
- The sanctions screener in the fan-out had no way to screen. It now has the `screen_counterparty` tool.
- The router sample's recorded decisions were illustrative. They are now a real recorded pass, and the chapter's table and discussion describe it.

## Not run

- The scripts are sized for a laptop and a handful of sample records. Nothing here has been run at volume, and the cost figures in `chapter5/costs.py` are arithmetic on stated assumptions, not measurements.
