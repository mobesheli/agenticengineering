"""Finance and engineering views backed by the same trace ledger."""

from __future__ import annotations

import html
from collections import defaultdict
from collections.abc import Sequence
from itertools import pairwise
from typing import Any

from .anomalies import robust_cost_anomalies
from .metrics import cost_per_outcome_by_plant, production_metrics
from .models import TraceRecord
from .pricing import reconciliation_summary


def _monthly_plant_reports(
    traces: Sequence[TraceRecord],
) -> dict[str, list[dict[str, Any]]]:
    by_period: dict[str, list[TraceRecord]] = defaultdict(list)
    for trace in traces:
        by_period[trace.period].append(trace)
    return {
        period: [row.model_dump() for row in cost_per_outcome_by_plant(rows)]
        for period, rows in sorted(by_period.items())
    }


def _discontinue_list(
    monthly: dict[str, list[dict[str, Any]]],
    *,
    consecutive_periods: int = 2,
) -> list[dict[str, Any]]:
    def month_index(period: str) -> int:
        year, month = (int(part) for part in period.split("-"))
        return year * 12 + month

    history: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for period, rows in monthly.items():
        for row in rows:
            history[(row["plant"], row["severity"])].append((period, row["verdict"]))
    flagged = []
    for (plant, severity), entries in sorted(history.items()):
        tail = entries[-consecutive_periods:]
        period_indexes = [month_index(period) for period, _ in tail]
        periods_are_consecutive = all(
            right - left == 1 for left, right in pairwise(period_indexes)
        )
        if (
            len(tail) == consecutive_periods
            and periods_are_consecutive
            and all(verdict == "above baseline" for _, verdict in tail)
        ):
            flagged.append(
                {
                    "plant": plant,
                    "severity": severity,
                    "periods": [period for period, _ in tail],
                    "reason": f"above baseline for {consecutive_periods} consecutive periods",
                }
            )
    return flagged


def build_finance_dashboard(
    traces: Sequence[TraceRecord],
    *,
    quarter_budget_usd: float,
    invoice_usd: float | None = None,
) -> dict[str, Any]:
    metrics = production_metrics(traces)
    estimated = float(metrics["machine_cost_usd"])
    monthly = _monthly_plant_reports(traces)
    by_plant = [row.model_dump() for row in cost_per_outcome_by_plant(traces)]
    invoice = estimated if invoice_usd is None else invoice_usd
    as_of = max(
        (trace.started_at.date().isoformat() for trace in traces), default="unknown"
    )
    return {
        "as_of": as_of,
        "headline": {
            "cost_per_approved_work_order_usd": metrics[
                "cost_per_successful_outcome_usd"
            ],
            "success_rate": metrics["success_rate"],
            "success_rate_ci_95": metrics["success_rate_ci_95"],
            "sample_size": metrics["attempts"],
            "spend_usd": metrics["fully_loaded_cost_usd"],
            "quarter_budget_usd": quarter_budget_usd,
            "budget_consumed": round(
                float(metrics["fully_loaded_cost_usd"]) / quarter_budget_usd,
                4,
            ),
            "cache_hit_rate": metrics["cache_hit_rate"],
        },
        "reconciliation": reconciliation_summary(estimated, invoice),
        "cost_per_outcome_by_plant": by_plant,
        "monthly": monthly,
        "discontinue_list": _discontinue_list(monthly),
        "drilldown_trace_ids": [trace.trace_id for trace in traces],
    }


def build_engineering_dashboard(traces: Sequence[TraceRecord]) -> dict[str, Any]:
    metrics = production_metrics(traces)
    expensive = sorted(
        traces, key=lambda trace: trace.fully_loaded_cost_usd, reverse=True
    )
    tool_failures: dict[str, dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "errors": 0}
    )
    for trace in traces:
        for span in trace.spans:
            if span.kind == "tool" and span.tool_name:
                tool_failures[span.tool_name]["calls"] += 1
                tool_failures[span.tool_name]["errors"] += int(span.status == "error")
    as_of = max(
        (trace.started_at.date().isoformat() for trace in traces), default="unknown"
    )
    return {
        "as_of": as_of,
        "headline": {
            key: metrics[key]
            for key in (
                "steps_per_task_p95",
                "tool_failure_rate",
                "loop_rate",
                "policy_denials",
                "model_refusals",
                "budget_stops",
            )
        },
        "tool_health": {
            name: {
                **counts,
                "failure_rate": round(counts["errors"] / counts["calls"], 4)
                if counts["calls"]
                else 0.0,
            }
            for name, counts in sorted(tool_failures.items())
        },
        "cost_anomalies": robust_cost_anomalies(traces),
        "expensive_traces": [
            {
                "trace_id": trace.trace_id,
                "plant": trace.identity.plant,
                "outcome": trace.outcome,
                "cost_usd": round(trace.fully_loaded_cost_usd, 4),
                "stop_reason": trace.stop_reason,
            }
            for trace in expensive[:10]
        ],
    }


def render_finance_dashboard(report: dict[str, Any]) -> str:
    """Render a dependency-free, drilldown-ready snapshot for the value review."""

    headline = report["headline"]
    tiles = [
        ("Cost / approved order", headline["cost_per_approved_work_order_usd"], "USD"),
        ("Success rate", round(headline["success_rate"] * 100, 1), "%"),
        ("Spend / budget", round(headline["budget_consumed"] * 100, 1), "%"),
        ("Cache-hit rate", round(headline["cache_hit_rate"] * 100, 1), "%"),
    ]
    tile_html = "".join(
        f'<section class="tile"><h2>{html.escape(label)}</h2><strong>{value}{suffix}</strong></section>'
        for label, value, suffix in tiles
    )
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(row['plant'])}</td>"
        f"<td>{html.escape(row['severity'])}</td>"
        f"<td>{row['attempts']}</td>"
        f"<td>{row['success_rate']:.1%}</td>"
        f"<td>{'$' + format(row['cost_per_outcome_usd'], '.2f') if row['cost_per_outcome_usd'] is not None else 'n/a'}</td>"
        f"<td>${row['baseline_usd']:.2f}</td>"
        f'<td class="{"bad" if row["verdict"] != "below baseline" else "good"}">{html.escape(row["verdict"])}</td>'
        "</tr>"
        for row in report["cost_per_outcome_by_plant"]
    )
    flagged = report["discontinue_list"]
    discontinue = (
        "<ul>"
        + "".join(
            f"<li>{html.escape(row['plant'])}, {html.escape(row['severity'])}: {html.escape(row['reason'])}</li>"
            for row in flagged
        )
        + "</ul>"
        if flagged
        else "<p>None.</p>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Chapter 9 value-review board</title>
<style>
body{{font:15px system-ui,sans-serif;margin:0;background:#0b1220;color:#e5edf8}}main{{max-width:1100px;margin:auto;padding:28px}}
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.tile{{background:#17233a;padding:18px;border-radius:10px}}
.tile h2{{font-size:13px;color:#a9b8cf;margin:0 0 10px}}.tile strong{{font-size:28px}}table{{width:100%;border-collapse:collapse;background:#111c30}}
th,td{{padding:10px;border-bottom:1px solid #293752;text-align:left}}th{{color:#a9b8cf}}.good{{color:#65d59a}}.bad{{color:#ff7a7a}}
.alert{{border-left:4px solid #ff5b5b;background:#2a1822;padding:12px 18px;margin-top:20px}}@media(max-width:760px){{.tiles{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main><h1>Maintenance agent value-review board</h1><p>As of {html.escape(report["as_of"])}. Every row links conceptually to the trace identifiers in the exported ledger.</p>
<div class="tiles">{tile_html}</div><h2>Cost per approved order, normalized by severity</h2>
<table><thead><tr><th>Plant</th><th>Severity</th><th>Attempts</th><th>Success</th><th>Cost / outcome</th><th>Baseline</th><th>Verdict</th></tr></thead><tbody>{rows}</tbody></table>
<section class="alert"><h2>Discontinue list</h2>{discontinue}</section></main></body></html>"""
