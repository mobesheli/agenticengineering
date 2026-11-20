"""Human approval, the alert triage pyramid, and the cost arithmetic."""

from datetime import UTC, datetime, timedelta

import pytest

from chapter5 import approvals, run_control, triage
from chapter5.approvals import (
    ApprovalStore,
    PaymentCase,
    advance_payment,
    hold_overdue,
    resume_payment,
)
from chapter5.costs import cost_per_call, triage_report
from chapter5.run_control import RetryLedger
from chapter5.triage import Desk, load_alerts, process_alert
from examples.scripted import INVESTIGATION_TURNS, TRIAGE_REPLIES, calls, says, scripted


@pytest.fixture
def paying(monkeypatch):
    def install(amount_cents: int, closing: str) -> None:
        approvals.RELEASED.clear()
        turns = [
            calls(
                "release_payment",
                {"payment_id": "pay-118", "amount_cents": amount_cents},
            ),
            says(closing),
        ]
        monkeypatch.setattr(
            approvals, "payments_agent", scripted(approvals.payments_agent, *turns)
        )

    return install


CASE = PaymentCase(
    case_id="case-118", request="Release pay-118.", evidence=["inv-552 matched"]
)


async def test_a_small_payment_is_released_without_a_pause(paying):
    paying(120_000, "Released.")

    status = await advance_payment(CASE, ApprovalStore())

    assert status.state == "closed" and approvals.RELEASED == {"pay-118": 120_000}


async def test_a_large_payment_pauses_and_survives_a_new_process(paying, tmp_path):
    path = str(tmp_path / "pending.db")
    paying(750_000, "Released after approval.")

    status = await advance_payment(CASE, ApprovalStore(path))
    assert status.state == "awaiting_approval" and approvals.RELEASED == {}

    done = await resume_payment("case-118", True, "", ApprovalStore(path))
    assert done.outcome == "Released after approval."
    assert approvals.RELEASED == {"pay-118": 750_000}


async def test_a_rejection_reaches_the_model_and_nothing_is_released(paying):
    pending = ApprovalStore()
    paying(750_000, "The reviewer declined. The payment was not released.")

    await advance_payment(CASE, pending)
    done = await resume_payment("case-118", False, "Beneficiary not verified.", pending)

    assert approvals.RELEASED == {} and "not released" in done.outcome


async def test_silence_is_not_consent(paying):
    pending = ApprovalStore()
    paying(750_000, "The payment stays on hold.")
    await advance_payment(CASE, pending)
    later = datetime.now(UTC) + timedelta(hours=5)

    assert await hold_overdue(pending, datetime.now(UTC)) == []
    held = await hold_overdue(pending, later)

    assert [h.state for h in held] == ["on_hold"] and approvals.RELEASED == {}


@pytest.fixture
def pyramid(monkeypatch):
    def install(alert_id: str) -> None:
        monkeypatch.setattr(
            triage,
            "alert_triage",
            scripted(triage.alert_triage, says(TRIAGE_REPLIES[alert_id])),
        )
        monkeypatch.setattr(
            run_control,
            "investigator",
            scripted(run_control.investigator, *INVESTIGATION_TURNS),
        )

    return install


@pytest.mark.parametrize(
    "alert_id, route",
    [
        ("alert-0001", "auto_cleared"),
        ("alert-0002", "analyst_review"),
        ("alert-0003", "human_confirm_clear"),
        ("alert-0004", "human_review"),
    ],
)
async def test_each_alert_takes_the_route_policy_gives_it(pyramid, alert_id, route):
    alert = next(a for a in load_alerts() if a.alert_id == alert_id)
    pyramid(alert_id)
    desk = Desk()

    disposition, investigation = await process_alert(alert, desk, RetryLedger())

    assert disposition.route == route
    assert (investigation is not None) == (route == "analyst_review")
    assert (alert_id in [a for a, _ in desk.people]) == (route != "auto_cleared")


async def test_an_unknown_alert_type_is_never_cleared_by_the_system(pyramid):
    alert = load_alerts()[0].model_copy(update={"alert_type": "new_typology"})
    pyramid("alert-0001")

    disposition, _ = await process_alert(alert, Desk(), RetryLedger())

    assert disposition.route == "human_confirm_clear"


def test_the_quality_sample_is_stable_and_close_to_its_share():
    picked = [n for n in range(50_000) if triage.in_quality_sample(f"alert-{n}")]

    assert 0.015 < len(picked) / 50_000 < 0.025
    assert triage.in_quality_sample("alert-7") == triage.in_quality_sample("alert-7")


def test_the_cost_arithmetic():
    assert float(cost_per_call("small", 3_000, 300)) == pytest.approx(0.00045)
    assert float(cost_per_call("frontier", 3_000, 300)) == pytest.approx(0.009)
    assert float(cost_per_call("frontier", 40_000, 4_000)) == pytest.approx(0.12)
    assert any("20 times" in line for line in triage_report())
