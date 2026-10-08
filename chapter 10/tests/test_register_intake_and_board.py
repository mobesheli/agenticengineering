from __future__ import annotations

from chapter10.adapter import adapt_legacy_report
from chapter10.board import board_rows, load_board
from chapter10.intake import recommend_route
from chapter10.models import IntakeRequest
from chapter10.register import FileRepository, run_listing_demo
from chapter10.switches import KillSwitchMap


def test_listing_is_refused_then_earned(tmp_path) -> None:
    refused, accepted = run_listing_demo(tmp_path / "register")
    assert not refused.accepted
    assert len(refused.missing) == 5
    assert accepted.accepted
    assert (tmp_path / "register/listing-results.json").is_file()


def test_repository_rejects_evidence_path_escape(tmp_path) -> None:
    repo = FileRepository(tmp_path)
    try:
        repo.resolve("../outside.json")
    except ValueError as exc:
        assert "escapes" in str(exc)
    else:
        raise AssertionError("repository accepted an escaping evidence path")


def test_legacy_suite_adapter_preserves_the_five_gate_fields() -> None:
    adapted = adapt_legacy_report(
        {
            "successes": 87,
            "cases": 100,
            "suite_version": "fraud-suite@12",
            "tokens": 44000,
        },
        bundle="invoice-triage@18.2",
        floor=0.85,
    )
    assert adapted.pass_rate == 0.87
    assert adapted.floor == 0.85
    assert adapted.suite == "fraud-suite@12"
    assert adapted.tokens == 44000


def test_intake_reuses_an_existing_agent_before_building() -> None:
    request = IntakeRequest(
        name="factory maintenance work order helper",
        purpose="draft a plant work order from sensor readings",
        audience="planners",
        reviewer="planner",
        data_tier="high",
        workflow_kind="company-specific",
        needs_internal_inspection=True,
    )
    recommendation = recommend_route(request)
    assert recommendation.route == "reuse"
    assert recommendation.match == "maintenance-planner"


def test_intake_routes_a_commodity_to_purchase() -> None:
    request = IntakeRequest(
        name="calendar helper",
        purpose="schedule internal meetings",
        audience="staff",
        reviewer="signed-in user",
        data_tier="low",
        workflow_kind="commodity",
        needs_internal_inspection=False,
    )
    assert recommend_route(request).route == "buy"


def test_intake_scaffolds_a_governed_build() -> None:
    request = IntakeRequest(
        name="alloy process optimizer",
        purpose="recommend company-specific furnace settings",
        audience="process engineers",
        reviewer="process engineer",
        data_tier="high",
        workflow_kind="company-specific",
        needs_internal_inspection=True,
    )
    recommendation = recommend_route(request)
    assert recommendation.route == "build"
    assert recommendation.scaffold["gate_mode"] == "monitor"


def test_board_keeps_metered_and_allocated_cost_visibly_distinct() -> None:
    rows = board_rows(load_board())
    assert {row["route"] for row in rows} == {"build", "join", "assemble", "buy"}
    bought = next(row for row in rows if row["route"] == "buy")
    assert bought["cost_source"] == "allocated"
    assert bought["drift_signals"] < bought["drift_total"]


def test_every_kill_switch_has_an_independent_owner_and_backup() -> None:
    switches = KillSwitchMap("maintenance-planner")
    status = switches.status()
    assert len(status) == 6
    assert all(switch.owner != switch.backup for switch in status)
    drill = switches.drill("gateway", target="Plant D")
    assert drill.active and drill.target == "Plant D"
    assert not next(s for s in switches.status() if s.name == "gateway").active
