from __future__ import annotations

from chapter9.maintenance import MaintenanceHarness, load_cases
from chapter9.metrics import (
    cost_per_outcome_by_plant,
    production_metrics,
    wilson_interval,
)


def test_full_fixture_emits_priced_outcome_labeled_traces() -> None:
    traces = MaintenanceHarness().run_all()
    assert len(traces) == len(load_cases()) == 24
    assert all(trace.identity.plant.startswith("Plant ") for trace in traces)
    assert all(trace.machine_cost_usd > 0 for trace in traces)
    assert all(trace.outcome is not None for trace in traces)
    assert all(
        span.attributes.get("price_card_version")
        for trace in traces
        for span in trace.spans
        if span.kind in {"generation", "tool"}
    )


def test_cost_per_outcome_is_fully_loaded_and_normalized_by_severity() -> None:
    report = cost_per_outcome_by_plant(MaintenanceHarness().run_all())
    by_plant = {row.plant: row for row in report}
    assert by_plant["Plant A"].verdict == "below baseline"
    assert by_plant["Plant B"].severity == "major"
    assert by_plant["Plant C"].severity == "critical"
    assert by_plant["Plant D"].verdict == "above baseline"
    assert by_plant["Plant D"].cost_per_outcome_usd > by_plant["Plant D"].baseline_usd


def test_production_metrics_keep_loops_stops_and_cost_visible() -> None:
    metrics = production_metrics(MaintenanceHarness().run_all())
    assert metrics["approved_outcomes"] == 14
    assert metrics["loop_rate"] > 0
    assert metrics["budget_stops"] == 1
    assert metrics["human_review_cost_usd"] > metrics["machine_cost_usd"]
    assert metrics["cache_hit_rate"] > 0.5
    assert metrics["tool_failure_rate"] == 0


def test_wilson_interval_is_bounded_on_small_cells() -> None:
    low, high = wilson_interval(1, 3)
    assert 0 <= low < 1 / 3 < high <= 1
