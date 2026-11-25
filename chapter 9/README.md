# Chapter 9: Measuring Agent Observability, Cost, and ROI

Companion code for Chapter 9 of *Agentic AI Engineering*. It instruments the
maintenance planning agent so that every run carries its identity, its price, and
its outcome, and it computes every figure in the chapter from those records.

Nothing here needs an API key except `examples/live_check.py`. The SDK runner, the
tools, the meter, the run budget, the guardrail, and the ledger are real. In the
examples, the model's replies and the token counts it reports are scripted, so
every dollar figure is the same on every run. All plant data is synthetic.

## Set up

```console
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Python 3.11 or later. The package versions are pinned in `requirements.txt`
(`openai-agents==0.24.0`).

## What is in the folder

| Path | What it is |
| --- | --- |
| `data/price-card.yaml` | The price card: model rates, tool fees, overheads, the reviewer's rate. Every cost comes from this file |
| `chapter9/pricecard.py` | Loads the card. A model or tool that is not on it is an error, never free |
| `chapter9/meter.py` | `price_usage`: one usage report split into five cost lines |
| `chapter9/budget.py` | `RunBudget`: dollars, model calls, and tool calls, reserved before each action. Children draw on the parent |
| `chapter9/metered.py` | `MeteredModel`: wraps any model, reserves before the call, prices after it, and writes the cost to the trace. `StepRouter`: a model for each step |
| `chapter9/guard.py` | The tool guardrail: tool fees and the repeated-call check |
| `chapter9/ledger.py` | `Ledger`: a trace processor that builds one record for each run and joins the outcome to it |
| `chapter9/border.py` | The border span around a call to another organization's agent |
| `chapter9/planner.py` | The maintenance planner: a diagnosis step and a drafting step |
| `chapter9/turn.py` | The anatomy of one turn, four ways |
| `chapter9/month.py` | Expands a month fixture into ledger records |
| `chapter9/report.py` | Unit cost, cost per approved order with intervals and verdicts, token share by step, metrics, reconciliation, the bill decomposition |
| `data/months/` | Three synthetic months: `before`, `candidate`, `after` |
| `examples/` | One runnable script for each result in the chapter |
| `outputs/` | What each example prints. The tests compare them |

## The examples

| Command | What it shows |
| --- | --- |
| `python -m examples.unit_cost` | Table 9.1: what one approved work order costs, line by line |
| `python -m examples.one_run` | One run span by span, on the frontier model and then routed and cached |
| `python -m examples.border` | The border span for a call to a supplier's agent |
| `python -m examples.one_turn` | One turn priced four ways (Figure 9.3) |
| `python -m examples.why_bill_rose` | Runs, tokens per run, and price; the reconciliation; the production metrics |
| `python -m examples.budget_stop` | Repeats refused, the run stopped by its budget, a child budget, an unpriced model |
| `python -m examples.token_share` | Model spend by step and model |
| `python -m examples.frontier` | Three configurations on cost per approved order (Figure 9.4) |
| `python -m examples.by_plant` | The finance view by plant and severity (Figure 9.5) |
| `python -m examples.live_check` | The planner against live models. Needs `OPENAI_API_KEY` |

The notebook `Chapter_9_Learning_Walkthrough.ipynb` runs the same examples in the
order of the chapter. Rebuild it with `python scripts/build_notebook.py`.

## Changing the numbers

Change a price in `data/price-card.yaml` or a group in `data/months/`, run the
examples again, and every figure follows. The tests in `tests/test_outputs.py` will
tell you which stored outputs changed.

The model names are in `chapter9/settings.py`. The prices were checked against the
provider's price list on the date at the top of the price card. Check them again
before you use the card for a decision.

## Exporting to your own trace store

The ledger in this folder keeps its records in memory, which is enough to compute
the reports. In production, add your exporter beside it with
`agents.tracing.add_trace_processor`, and send spans to the collector your platform
already runs. Redact payloads before export, as Chapter 8 showed.
