from __future__ import annotations

from chapter9.maintenance import MaintenanceHarness
from chapter9.routing import (
    choose_cheapest_acceptable,
    load_candidates,
    pareto_frontier,
    routing_change_gate,
    token_share_by_step,
)


def test_token_share_reveals_the_expensive_steps() -> None:
    shares = token_share_by_step(MaintenanceHarness().run_all())
    assert shares
    assert sum(row["cost_share"] for row in shares.values()) > 0.99
    assert any(key.startswith("plan/") for key in shares)
    assert all(row["calls"] > 0 for row in shares.values())


def test_pareto_frontier_removes_expensive_worse_configurations() -> None:
    names = {candidate.name for candidate in pareto_frontier(load_candidates())}
    assert "mid-high" not in names
    assert "frontier-low" not in names
    assert "frontier-high" in names


def test_cheapest_configuration_above_floor_is_selected_and_gated() -> None:
    candidates = load_candidates()
    selected = choose_cheapest_acceptable(candidates, quality_floor=0.90)
    old = next(
        candidate for candidate in candidates if candidate.name == "frontier-medium"
    )
    assert selected.name == "mid-medium"
    verdict = routing_change_gate(old, selected, quality_floor=0.90)
    assert verdict["status"] == "accept"
    assert verdict["cost_change_percent"] < 0
