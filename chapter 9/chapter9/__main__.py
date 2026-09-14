"""Run the Chapter 9 offline value-review pattern."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .dashboard import build_engineering_dashboard, build_finance_dashboard
from .evidence import emit_value_evidence, verify_manifest
from .live import build_maintenance_agent, make_live_context, run_live_case
from .maintenance import MaintenanceHarness, load_cases
from .telemetry import export_traces_to_otlp


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "--case-id", help="run one synthetic case instead of the full fixture"
    )
    command.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evidence/latest"),
        help="review artifact destination",
    )
    command.add_argument("--quarter-budget-usd", type=float, default=250.0)
    command.add_argument("--invoice-usd", type=float)
    command.add_argument("--export-otlp", action="store_true")
    command.add_argument(
        "--otel-endpoint",
        default="http://localhost:4318/v1/traces",
    )
    command.add_argument("--show-live-wiring", action="store_true")
    command.add_argument("--live", action="store_true")
    return command


def select_cases(case_id: str | None):
    cases = load_cases()
    if case_id is None:
        return cases
    selected = [case for case in cases if case.case_id == case_id]
    if not selected:
        raise SystemExit(f"unknown case id: {case_id}")
    return selected


def main() -> None:
    args = parser().parse_args()
    cases = select_cases(args.case_id)
    if args.show_live_wiring:
        context = make_live_context(cases[0])
        agent = build_maintenance_agent(context)
        print(
            json.dumps(
                {
                    "agent": agent.name,
                    "model_adapter": type(agent.model).__name__,
                    "tools": [tool.name for tool in agent.tools],
                    "guardrails_per_tool": [
                        len(tool.tool_input_guardrails) for tool in agent.tools
                    ],
                    "budget": context.budget.snapshot(),
                },
                indent=2,
            )
        )
        if not args.live:
            return
    if args.live:
        result = asyncio.run(run_live_case(cases[0]))
        print(result.model_dump_json(indent=2))
        return

    harness = MaintenanceHarness()
    traces = harness.run_all(cases)
    manifest = emit_value_evidence(
        traces,
        args.output_dir,
        quarter_budget_usd=args.quarter_budget_usd,
        invoice_usd=args.invoice_usd,
    )
    sent = 0
    if args.export_otlp:
        sent = export_traces_to_otlp(traces, endpoint=args.otel_endpoint)
    finance = build_finance_dashboard(
        traces,
        quarter_budget_usd=args.quarter_budget_usd,
        invoice_usd=args.invoice_usd,
    )
    engineering = build_engineering_dashboard(traces)
    print(
        json.dumps(
            {
                "trace_count": len(traces),
                "manifest": str(manifest),
                "manifest_verified": verify_manifest(manifest),
                "headline": finance["headline"],
                "discontinue_list": finance["discontinue_list"],
                "engineering": engineering["headline"],
                "otlp_spans_sent": sent,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
