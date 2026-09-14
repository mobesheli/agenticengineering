"""Build the checked-in Chapter 9 learning walkthrough deterministically."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "Chapter_9_Watching_the_Money_and_the_Machines_Learning_Walkthrough.ipynb"
)


def clean(text: str) -> str:
    return dedent(text).strip() + "\n"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(clean(text))


def code(text: str):
    return nbf.v4.new_code_cell(clean(text))


cells = [
    markdown(
        """
        # Chapter 9: Watching the Money and the Machines

        **Observability, cost, and the ROI case — a runnable learning walkthrough**

        This notebook turns a synthetic maintenance-planning workflow into the record both engineering and finance need: every run carries caller-derived identity, a versioned price, a deterministic budget, and a business outcome. The default path is offline. It makes no model calls, needs no credential, and produces the same teaching results on every run.

        The optional final section shows the pinned OpenAI Agents SDK wiring without calling a model. A live call happens only when you set both `OPENAI_API_KEY` and `CHAPTER9_RUN_LIVE=1` yourself.
        """
    ),
    markdown(
        """
        ## Start here

        Run the cells from top to bottom once. The sequence mirrors the chapter:

        1. Build Total Cost of Ownership (TCO), not a token-only estimate.
        2. Read one agent run as a trace and expose a zero-error loop.
        3. Normalize SDK usage fields and price every generation from a versioned card.
        4. Carry identity and receipts across internal and counterparty boundaries.
        5. Compute paired production metrics with bounded uncertainty.
        6. Stop repeated or over-budget actions before they spend.
        7. Route by measured step cost and the cost-quality frontier.
        8. Generate finance and engineering views from the same ledger.
        9. Export a hashed value-review evidence pack and, optionally, local OTLP traces.
        """
    ),
    markdown("## 0. Setup"),
    code(
        """
        from __future__ import annotations

        import json
        import os
        import sys
        import tempfile
        from pathlib import Path

        chapter_root = Path.cwd()
        if not (chapter_root / "chapter9").exists():
            candidate = chapter_root / "chapter 9"
            if candidate.exists():
                chapter_root = candidate
        if str(chapter_root) not in sys.path:
            sys.path.insert(0, str(chapter_root))

        from chapter9.border import call_counterparty
        from chapter9.budget import LoopDetected, RunBudget
        from chapter9.anomalies import credit_depletion_state, detector_coverage
        from chapter9.dashboard import build_engineering_dashboard, build_finance_dashboard
        from chapter9.evidence import emit_value_evidence, verify_manifest
        from chapter9.live import build_maintenance_agent, make_live_context, run_live_case
        from chapter9.maintenance import MaintenanceHarness, load_cases
        from chapter9.metrics import cost_per_outcome_by_plant, production_metrics
        from chapter9.pricing import load_price_card, normalize_usage, price_model_usage
        from chapter9.replay import ActivityJournal
        from chapter9.quality import JudgeCalibrationMonitor, calibration_report, stable_human_review_sample
        from chapter9.routing import (
            choose_cheapest_acceptable,
            load_candidates,
            pareto_frontier,
            routing_change_gate,
            token_share_by_step,
        )

        cases = load_cases()
        harness = MaintenanceHarness()
        traces = harness.run_all(cases)
        card = load_price_card()
        print(f"Loaded {len(cases)} synthetic cases and emitted {len(traces)} traces.")
        """
    ),
    markdown(
        """
        ## 1. What the CFO actually wants to know

        Token price is one line in TCO. The denominator matters just as much: all attempts cost money, while only business-accepted outcomes count as successes. The companion therefore defines cost per successful outcome as fully loaded cost across every attempt divided by approved work orders.

        The synthetic review rate is `$0.98` per minute, matching the chapter's illustrative `$2.94` for a three-minute review. It is intentionally larger than the model line so an optimization targets the real cost rather than the most fashionable one.
        """
    ),
    code(
        """
        metrics = production_metrics(traces)
        {
            "attempts": metrics["attempts"],
            "approved_outcomes": metrics["approved_outcomes"],
            "machine_cost_usd": metrics["machine_cost_usd"],
            "human_review_cost_usd": metrics["human_review_cost_usd"],
            "cost_per_successful_outcome_usd": metrics["cost_per_successful_outcome_usd"],
        }
        """
    ),
    code(
        """
        [row.model_dump() for row in cost_per_outcome_by_plant(traces)]
        """
    ),
    markdown(
        """
        Plant D is above the human baseline, while Plants A, B, and C are below their severity-specific baselines. Normalizing by severity avoids punishing a plant simply because it handles harder failures.
        """
    ),
    markdown(
        """
        ## 2. Tracing the machines: from spans to answers

        A green request is not enough. The trace waterfall reveals what the agent did inside the request: generations, tools, retries, loops, reasoning, duration, and cost.

        ![A maintenance-agent trace waterfall](assets/figure_9_1_trace_viewer.png)
        """
    ),
    code(
        """
        sample = next(trace for trace in traces if trace.identity.plant == "Plant B")
        [
            {
                "kind": span.kind,
                "name": span.name,
                "step": span.step_type,
                "duration_ms": span.duration_ms,
                "cost_usd": round(span.cost_usd, 5),
                "status": span.status,
                "reason": span.attributes.get("reason"),
            }
            for span in sample.spans
        ]
        """
    ),
    markdown(
        """
        The denied `loop_breaker` span is a healthy control, not an application error. It proves the harness noticed an identical parts lookup and refused to buy it twice.
        """
    ),
    markdown(
        """
        ### A thin usage translation layer

        The checked-in processor accepts flat teaching fields and the pinned SDK's nested `input_tokens_details` and `output_tokens_details`. Everything downstream reads the normalized shape. Provider or SDK naming changes therefore touch one adapter rather than every dashboard.
        """
    ),
    code(
        """
        sdk_shaped_usage = {
            "input_tokens": 10_000,
            "input_tokens_details": {"cached_tokens": 6_000, "cache_write_tokens": 1_000},
            "output_tokens": 2_000,
            "output_tokens_details": {"reasoning_tokens": 1_200},
        }
        normalized = normalize_usage(sdk_shaped_usage)
        cost = price_model_usage(normalized, model="maintenance-mid", card=card)
        {"normalized": normalized.model_dump(), "cost": cost.model_dump(), "total": cost.total}
        """
    ),
    markdown(
        """
        The five cost fields suggest five different fixes: stabilize an uncached prefix, reuse cache writes, lower reasoning effort, constrain visible output, or route the step to a smaller model. An unexplained total cannot tell you which lever to pull.

        ![Trace propagation through the harness and across partner borders](assets/figure_9_2_trace_propagation.png)
        """
    ),
    markdown("### Counterparty receipts and replay without repeated effects"),
    code(
        """
        from dataclasses import dataclass

        @dataclass
        class Reply:
            status: str
            task_id: str
            server_info: dict
            metadata: dict

        class SyntheticSupplier:
            def __init__(self):
                self.calls = 0
            def send(self, task, *, headers):
                self.calls += 1
                return Reply(
                    status="retry" if self.calls == 1 else "completed",
                    task_id="supplier-task-42",
                    server_info={"name": "synthetic-supplier", "version": "2"},
                    metadata={"cost": 0.08, "receipt_id": "receipt-9"},
                )

        supplier = SyntheticSupplier()
        _, receipt = call_counterparty(
            supplier,
            {"part": "PART-BEARING-A"},
            tenant="heavy-things-manufacturing",
            case_id="case-9",
        )
        receipt
        """
    ),
    code(
        """
        journal = ActivityJournal()
        journal.record(
            activity_id="tool-write-1",
            kind="tool",
            name="write_work_order",
            request={"asset_id": "A-PUMP-14"},
            response={"work_order": "WO-RECORDED-1"},
        )
        journal.replay()
        """
    ),
    markdown(
        """
        The border receipt keeps a correlation identifier, remote task identifier, attempts, latency, quoted cost, and receipt identifier. It explicitly does not turn correlation metadata into permission. The replay reads the recorded tool result instead of writing the work order a second time.
        """
    ),
    markdown("### Keep production judges calibrated"),
    code(
        """
        monitor = JudgeCalibrationMonitor(minimum_kappa=0.50, maximum_drop=0.10)
        july = calibration_report(
            period="2026-07",
            judge_version="judge-v1",
            human_labels=["pass", "pass", "fail", "fail", "pass", "fail"],
            judge_labels=["pass", "pass", "fail", "fail", "pass", "pass"],
        )
        august = calibration_report(
            period="2026-08",
            judge_version="judge-v2",
            human_labels=["pass", "pass", "fail", "fail", "pass", "fail"],
            judge_labels=["pass", "pass", "pass", "pass", "pass", "pass"],
        )
        {
            "july": monitor.add(july),
            "august": monitor.add(august),
            "fresh_human_sample": stable_human_review_sample(
                [trace.trace_id for trace in traces], sample_size=5, seed=9
            ),
        }
        """
    ),
    markdown(
        """
        Raw agreement can remain flattering when one class dominates. The monitor watches Cohen's kappa against fresh human labels, triggers when agreement beyond chance drops, and always requires fresh calibration after a judge-version change. The sampler is seeded by the evaluation service, not by the agent, and the live agent has no grader or telemetry tool.

        Cost alerting needs the same explicit coverage discipline:
        """
    ),
    code(
        """
        {
            "credit_state": credit_depletion_state(spent_usd=80, limit_usd=100),
            "coverage": detector_coverage(
                {"cloud": ["service", "account", "region"]},
                required_dimensions=["service", "account", "region", "plant", "principal"],
            ),
        }
        """
    ),
    markdown(
        """
        The cloud detector covers infrastructure dimensions but misses plant and principal, so the application telemetry must fill that gap. The credit policy warns at half remaining and pages at one fifth remaining rather than waiting for a delayed daily budget alert.
        """
    ),
    markdown("## 3. The real cost and the brake"),
    markdown(
        """
        ![Naive and optimized cost anatomy of one turn](assets/figure_9_3_turn_cost.png)

        Versioned pricing is an estimate; the invoice remains the truth. The run budget is still enforced against the estimate before every metered action, because a next-day cloud alert cannot stop today's loop.
        """
    ),
    code(
        """
        demo_budget = RunBudget(
            price_card=card,
            limit_usd=0.10,
            max_calls=4,
            max_steps=4,
            max_seconds=30,
        )
        args = {"asset_id": "A-PUMP-14", "fault_code": "TEMP_DRIFT"}
        reservation = demo_budget.reserve_tool("check_parts_catalog", args)
        demo_budget.settle(reservation, card.tool_cost("check_parts_catalog"))
        try:
            demo_budget.reserve_tool("check_parts_catalog", args)
        except LoopDetected as exc:
            loop_result = str(exc)
        {"loop_result": loop_result, "budget": demo_budget.snapshot()}
        """
    ),
    markdown(
        """
        This is a content-level refusal: the model can reuse the prior result and continue. A reservation that would cross the dollar, call, step, or wall-clock allowance raises a run-stopping error instead. Unknown models and tools are errors, never free entries.
        """
    ),
    markdown("## 4. Model routing as cost control"),
    markdown(
        """
        ![Cost-quality frontier and reasoning effort shapes](assets/figure_9_4_cost_quality_frontier.png)

        The useful configuration is the cheapest point above the acceptance floor, with retries and fallbacks folded into cost. The router starts from observed spans: which step and model consumed the budget?
        """
    ),
    code(
        """
        token_share_by_step(traces)
        """
    ),
    code(
        """
        candidates = load_candidates()
        frontier = pareto_frontier(candidates)
        selected = choose_cheapest_acceptable(candidates, quality_floor=0.90)
        old = next(candidate for candidate in candidates if candidate.name == "frontier-medium")
        {
            "frontier": [candidate.name for candidate in frontier],
            "selected": selected.model_dump(),
            "change_gate": routing_change_gate(old, selected, quality_floor=0.90),
        }
        """
    ),
    markdown(
        """
        The illustrative move from `frontier-medium` to `mid-medium` clears the quality floor and reduces cost per accepted outcome. A configuration that is merely cheaper does not ship; it must also clear the paired quality gate.
        """
    ),
    markdown("## 5. One ledger, two screens"),
    markdown(
        """
        ![Finance-first value-review dashboard](assets/figure_9_5_value_dashboard.png)

        Finance opens on unit economics and the discontinue list. Engineering opens on p95 steps, loops, tool failures, policy denials, model refusals, budget stops, and expensive traces. Both views drill into the same trace identifiers.
        """
    ),
    code(
        """
        finance = build_finance_dashboard(traces, quarter_budget_usd=250.0)
        engineering = build_engineering_dashboard(traces)
        {
            "finance_headline": finance["headline"],
            "discontinue_list": finance["discontinue_list"],
            "engineering_headline": engineering["headline"],
            "same_ledger": set(finance["drilldown_trace_ids"]) == {trace.trace_id for trace in traces},
        }
        """
    ),
    markdown("### Export the value-review evidence"),
    code(
        """
        evidence_dir = Path(tempfile.mkdtemp(prefix="chapter9-evidence-"))
        manifest = emit_value_evidence(traces, evidence_dir, quarter_budget_usd=250.0)
        {
            "manifest": str(manifest),
            "verified": verify_manifest(manifest),
            "artifacts": sorted(path.name for path in evidence_dir.iterdir()),
        }
        """
    ),
    markdown(
        """
        Open `value_review.html` for the self-contained finance snapshot. `priced_traces.jsonl` is the drilldown ledger, the two JSON files are the finance and engineering views, `token_share_by_step.json` is routing evidence, and the manifest hashes every artifact.

        ### Optional local observability stack

        The repository includes Grafana's all-in-one development image with the OpenTelemetry Collector, Tempo, Loki, Prometheus, and Grafana. From a terminal in `chapter 9`:

        ```bash
        docker compose up -d
        python -m chapter9 --export-otlp --output-dir evidence/local
        open http://localhost:3000
        ```

        The generated finance board remains the value view. Grafana/Tempo is the trace investigation view. This cell does not start Docker or perform network I/O.
        """
    ),
    markdown("## 6. Optional Agents SDK wiring"),
    code(
        """
        live_context = make_live_context(cases[0])
        live_agent = build_maintenance_agent(live_context)
        {
            "agent": live_agent.name,
            "model_adapter": type(live_agent.model).__name__,
            "tools": [tool.name for tool in live_agent.tools],
            "guardrails_per_tool": [len(tool.tool_input_guardrails) for tool in live_agent.tools],
            "has_execution_tool": any("execute" in tool.name or "approve" in tool.name for tool in live_agent.tools),
            "budget": live_context.budget.snapshot(),
        }
        """
    ),
    code(
        """
        if os.getenv("OPENAI_API_KEY") and os.getenv("CHAPTER9_RUN_LIVE") == "1":
            live_result = await run_live_case(cases[0])
            live_result.model_dump()
        else:
            print("Live call skipped. Set OPENAI_API_KEY and CHAPTER9_RUN_LIVE=1 to opt in.")
        """
    ),
    markdown(
        """
        The live adapter reserves an illustrative model-call ceiling before every non-streamed request and uses a tool-input guardrail before every tool call. It exposes only read tools and returns a proposal; approval and execution remain outside the agent. Replace the illustrative price-card entries with your contracted rates before treating its cost as financial evidence.

        ## What to carry into production

        - Derive tenant, plant, principal, and severity outside the model path.
        - Normalize usage once and version the price card used for every estimate.
        - Keep the collector, graders, and metric store outside the agent's credentials.
        - Reserve budget before model and tool calls; fail closed on unknown prices.
        - Count repeated successful calls as loops even when the error rate is zero.
        - Replay recorded effects; rerun only an explicit fork.
        - Compare fully loaded cost per accepted outcome against a measured human baseline.
        - Route each step to the cheapest configuration that clears a paired quality gate.
        - Put above-baseline workflows on a visible discontinue list and act on it.
        """
    ),
]

for index, cell in enumerate(cells):
    cell["id"] = f"chapter9-{index:03d}"

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
    },
)
nbf.write(notebook, OUTPUT)
print(OUTPUT)
