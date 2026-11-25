# Verification record: Chapter 9

Checked on 25 November 2026 with Python 3.13, openai-agents 0.24.0, openai 3.55.0,
pydantic 2.14.3.

## What was run

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 46 passed |
| `ruff format --check .` and `ruff check .` | clean |
| Every example under `examples/` except `live_check` | output identical to `outputs/` |
| `python scripts/build_notebook.py` | 25 cells, 0 errors |
| `python -m examples.live_check 5` against live models | 7 of 7 as intended |
| Every code and console block printed in the chapter | found in this folder, character for character |

## SDK interfaces the code relies on, checked against the installed package

- `agents.Model.get_response` and `stream_response`: wrapped by `MeteredModel`.
- `agents.usage.Usage`: `input_tokens`, `output_tokens`,
  `input_tokens_details.cached_tokens`, `input_tokens_details.cache_write_tokens`,
  `output_tokens_details.reasoning_tokens`. Cached and cache-write tokens are part
  of the input count, and reasoning tokens are part of the output count.
- `agents.custom_span`, and `span.span_data.data` for adding fields before the
  span closes.
- `agents.tracing.processor_interface.TracingProcessor` and
  `agents.tracing.set_trace_processors`. A run produces a task span, an agent
  span, a turn span for each turn, and a function span for each tool call. The
  trace export carries `workflow_name` and `metadata`.
- Tool input guardrails: `ToolGuardrailFunctionOutput.allow`, `reject_content`,
  and `raise_exception`. A refused call still produces a function span, whose
  output is the refusal message. `raise_exception` ends the run with
  `ToolInputGuardrailTripwireTriggered`, and the stopped call's function span
  carries an error.
- `agents.testing.ScriptedModel` with `ModelStep(output=..., usage=...)`.

## The live run

`examples/live_check.py` was run on 25 November 2026 with a temporary key, against
the three models in `chapter9/settings.py`. Five full runs, one run with a
two-cent budget, and one streamed call:

- Every model call was priced from the provider's own usage report, on both the
  plain and the streamed path. Reasoning tokens were reported and priced.
- Each step went to the model chosen for it, and the run carried its identity.
- The budget and the ledger agreed to the cent on every run.
- The two-cent run stopped at a tool call after spending $0.0113, and the caller
  received `BudgetExceeded`.
- The prompts in this folder are too short for the provider to cache, so the
  live run reported no cached tokens. The cached and cache-write lines are
  covered by the tests with scripted usage, not by the live run.

The first live run found three faults that the scripted runs had not, and all
three are fixed and now covered by tests:

1. A budget stop at a tool call reached the caller as the SDK's tripwire
   exception and not as `BudgetExceeded`. `plan_work_order` now converts it, so
   a caller handles one kind of stop.
2. The ledger charged the fee for a tool call that the budget had stopped. It
   now records that call as stopped, with no fee.
3. `search_manual` matched only an exact phrase, and `check_parts` failed on a
   part number it did not know. Both now answer the way a real tool would.

## Prices

`data/price-card.yaml` holds the provider's published standard-tier prices for
the three models, checked on the date in the file. Tool fees, overheads, the
reviewer's rate, the baseline, and the three months of runs are illustrative.
