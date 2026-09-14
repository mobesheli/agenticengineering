# Chapter 9 Companion Repo

This folder contains the runnable companion for Chapter 9, *Watching the Money and the Machines: Observability, Cost, and the ROI Case*.

Start with `Chapter_9_Watching_the_Money_and_the_Machines_Learning_Walkthrough.ipynb`. It follows the draft section by section: fully loaded unit economics, priced traces, identity and outcome joins, counterparty receipts, safe replay, per-run budgets, loop blocking, per-step token shares, model routing, paired quality gates, and a value-review board shared by engineering and finance.

The default path is deterministic and offline. It uses 24 synthetic maintenance cases across four plants and two monthly periods. It needs no API key, sends no telemetry, and makes no model calls.

## Start Here

Use this order on a first pass:

1. Run the synthetic maintenance workload and inspect one trace waterfall.
2. Normalize nested SDK usage fields and price them against the versioned card.
3. Compare machine cost with reviewer cost and the measured human baseline.
4. Trigger the exact-call loop breaker and the run-budget stop.
5. Replay a recorded effect without executing it twice.
6. Group token and cost shares by orchestration step and model.
7. Select the cheapest routing configuration above the quality floor.
8. Generate the finance and engineering views from the same trace ledger.
9. Put Plant D on the discontinue list after two consecutive above-baseline periods.
10. Export the hashed value-review evidence pack.

## One-Time Setup

Python 3.11 or later is required. Python 3.12 is recommended.

```bash
cd "chapter 9"
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Open the walkthrough:

```bash
jupyter notebook Chapter_9_Watching_the_Money_and_the_Machines_Learning_Walkthrough.ipynb
```

## Run the Offline Value Review

Run all 24 cases and write the evidence pack:

```bash
python -m chapter9 --output-dir evidence/latest
```

The command emits:

- `priced_traces.jsonl`: the drilldown ledger with identity, spans, usage, cost, and outcome
- `finance_dashboard.json`: fully loaded cost per approved work order, uncertainty, budget, reconciliation, monthly trends, and discontinue list
- `engineering_dashboard.json`: p95 steps, loop and failure rates, separated denials/refusals, budget stops, and expensive traces
- `token_share_by_step.json`: per-step, per-model tokens and cost share for routing
- `value_review.html`: a dependency-free finance snapshot
- `manifest.json`: SHA-256 hashes for every artifact

Run one case:

```bash
python -m chapter9 --case-id 2026-07-B-001 --output-dir evidence/one-case
```

Inspect the live SDK structure without making a model call:

```bash
python -m chapter9 --show-live-wiring
```

## Watch Traces Locally

`compose.yaml` uses Grafana's [all-in-one OpenTelemetry development image](https://github.com/grafana/docker-otel-lgtm). One container provides an OpenTelemetry Collector, Tempo, Loki, Prometheus, and Grafana. This is a local learning stack, not a production topology.

```bash
docker compose up -d
python -m chapter9 --export-otlp --output-dir evidence/local
open http://localhost:3000
```

The provisioned home dashboard points to recent `chapter9-maintenance` traces. Open Grafana Explore with the Tempo data source to query the plant, severity, outcome, model/tool, and cost span attributes.

Stop the stack when finished:

```bash
docker compose down
```

## Optional Live Route

The live agent exposes only three synthetic read tools. Every tool has a pre-call budget guardrail, and the model adapter reserves a configured token ceiling before each non-streamed request. The agent returns a proposal and has no approval or execution tool.

```bash
test -n "$OPENAI_API_KEY"
python -m chapter9 --live --case-id 2026-07-A-001
```

The project never creates, copies, logs, or persists credentials. `OPENAI_API_KEY` is read only from the caller's environment. The live adapter defaults to `gpt-5-mini`; change the model deliberately in `chapter9/live.py` and update the corresponding price-card mapping before using the result as cost evidence.

## Project Map

- `Chapter_9_Watching_the_Money_and_the_Machines_Learning_Walkthrough.ipynb`: guided reader experience
- `chapter9/models.py`: typed price, usage, trace, case, value, and routing contracts
- `chapter9/pricing.py`: usage-field normalization, versioned pricing, and invoice reconciliation
- `chapter9/tracing.py`: append-style in-memory ledger and identity/outcome joins
- `chapter9/sdk.py`: pinned Agents SDK `TracingProcessor` adapter
- `chapter9/budget.py`: pre-call dollar, call, step, time, and loop controls
- `chapter9/maintenance.py`: complete deterministic maintenance workload
- `chapter9/metrics.py`: production metrics, Wilson intervals, and severity-normalized unit economics
- `chapter9/quality.py`: human-label sampling, Cohen's kappa, and judge recalibration tripwires
- `chapter9/anomalies.py`: credit-depletion alerts, detector coverage, and robust per-workload cost anomalies
- `chapter9/routing.py`: per-step token share, Pareto frontier, and routing gate
- `chapter9/border.py`: counterparty correlation and receipt record
- `chapter9/replay.py`: event-sourced replay and explicit forks
- `chapter9/dashboard.py`: finance and engineering views plus the HTML board
- `chapter9/evidence.py`: review artifacts and hashed manifest
- `chapter9/telemetry.py`: deliberate OTLP/HTTP export to the local stack
- `chapter9/live.py`: optional budgeted OpenAI Agents SDK adapter
- `data/fixtures/`: synthetic maintenance cases
- `data/pricing/`: illustrative, versioned price card
- `data/baselines/`: illustrative pre-deployment human cost by severity
- `data/routing/`: illustrative cost-quality configurations
- `observability/`: provisioned Grafana dashboard
- `assets/`: the five Chapter 9 figures
- `tests/`: offline unit, integration, SDK-wiring, CLI, and evidence tests

## Verify Everything

Run the complete offline suite:

```bash
pytest -q
```

Rebuild and execute the checked-in notebook:

```bash
python scripts/build_notebook.py
jupyter nbconvert --to notebook --execute \
  Chapter_9_Watching_the_Money_and_the_Machines_Learning_Walkthrough.ipynb \
  --output /tmp/chapter9-executed.ipynb \
  --ExecutePreprocessor.timeout=180
```

Run the CLI smoke test directly:

```bash
python -m chapter9 --output-dir /tmp/chapter9-evidence
```

## Cost and Trust Boundaries

- Every checked-in number, model tier, baseline, and price is illustrative synthetic data, not a customer disclosure or a current provider quote.
- Replace the price card with contracted rates and reconcile estimated span cost to the invoice before using it for chargeback.
- Unknown models and tools fail closed; they are never assigned a zero price.
- Plant, principal, severity, and baseline come from application context rather than model output.
- High-cardinality identity stays on traces. Dashboard metrics use bounded plant, severity, workflow, outcome, and model categories.
- The run budget reserves before calls. Cloud budgets and provider caps remain slower backstops.
- A repeated call is recorded as a loop denial even when the application error rate is zero.
- Replay returns recorded model and tool results. Only an explicit fork may recompute an activity.
- The local ledger and HTML board are teaching implementations. Production deployments should use append-only, access-separated telemetry and outcome stores.
