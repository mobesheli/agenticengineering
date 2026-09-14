from __future__ import annotations

import json

from chapter9.dashboard import build_engineering_dashboard, build_finance_dashboard
from chapter9.evidence import emit_value_evidence, verify_manifest
from chapter9.maintenance import MaintenanceHarness


def test_two_dashboard_views_drill_into_the_same_ledger() -> None:
    traces = MaintenanceHarness().run_all()
    finance = build_finance_dashboard(traces, quarter_budget_usd=250, invoice_usd=4.0)
    engineering = build_engineering_dashboard(traces)
    assert set(finance["drilldown_trace_ids"]) == {trace.trace_id for trace in traces}
    assert engineering["headline"]["budget_stops"] == 1
    assert finance["reconciliation"]["within_tolerance"]


def test_two_bad_months_put_plant_d_on_the_discontinue_list() -> None:
    report = build_finance_dashboard(
        MaintenanceHarness().run_all(),
        quarter_budget_usd=250,
    )
    assert report["discontinue_list"] == [
        {
            "plant": "Plant D",
            "severity": "routine",
            "periods": ["2026-07", "2026-08"],
            "reason": "above baseline for 2 consecutive periods",
        }
    ]


def test_evidence_pack_is_complete_and_hash_verified(tmp_path) -> None:
    traces = MaintenanceHarness().run_all()
    manifest = emit_value_evidence(traces, tmp_path)
    assert verify_manifest(manifest)
    payload = json.loads(manifest.read_text())
    assert payload["trace_count"] == 24
    assert {row["path"] for row in payload["records"]} == {
        "finance_dashboard.json",
        "engineering_dashboard.json",
        "token_share_by_step.json",
        "priced_traces.jsonl",
        "value_review.html",
    }
