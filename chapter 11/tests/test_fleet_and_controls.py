from decimal import Decimal

import pytest

from chapter11.artifacts import load_json
from chapter11.board import load_register
from chapter11.controls import (
    Mandate,
    MandateLedger,
    drill_report,
    improvement_gate,
    severe_alert_action,
)
from chapter11.fleet import contract_gaps, pager, reconcile


def test_registry_reconciliation_keeps_accountability_and_flags_live_residue():
    findings = reconcile(load_register(), load_json("identities.json"), day=240)
    by_agent = {f["agent"]: f["gaps"] for f in findings}
    assert "unregistered identity" in by_agent["cloud-only-1"]
    assert "provider access bypasses the gateway" in by_agent["direct-model-helper"]
    assert "live identity for inactive agent" in by_agent["retired-alert-helper"]
    assert "another registry" in by_agent["medication-reconciliation"][0]
    assert len(load_register()) == 15


def test_consumer_contracts_catch_breaks_and_sunset():
    contract = load_json("parts-contract.json")
    response = {"part_id": "bearing", "lead_time_days": 2, "available_quantity": 3}
    assert contract_gaps(contract, response, call_version=2, day=329) == []
    assert "sunset" in contract_gaps(contract, response, call_version=2, day=330)[0]
    response["lead_time_days"] = "tomorrow"
    assert (
        "maintenance-planner"
        in contract_gaps(contract, response, call_version=3, day=330)[0]
    )


def test_two_pagers():
    entry = load_register()[0]
    assert pager(entry, "infrastructure") == "platform-rotation"
    assert pager(entry, "behavior") == entry.owner


def ledger():
    return MandateLedger(
        Mandate(
            mandate_id="mandate-1",
            agent="procurement",
            authorized_by="Finance owner",
            instrument="purchase-account",
            suppliers=["catalog-supplier"],
            transaction_cap=Decimal(60),
            daily_cap=Decimal(100),
            expires_day=30,
        )
    )


def order(book, order_id="one", **kwargs):
    return book.reserve(
        **dict(
            order_id=order_id,
            agent="procurement",
            supplier="catalog-supplier",
            instrument="purchase-account",
            amount=Decimal(50),
            day=1,
            **kwargs,
        )
    )


def test_mandate_daily_limit_idempotency_and_revocation():
    book = ledger()
    order(book)
    order(book)
    order(book, "two")
    with pytest.raises(ValueError, match="daily cap"):
        order(book, "three")
    assert book.revoke()["in_flight_orders"] == ["one", "two"]
    with pytest.raises(ValueError, match="revoked"):
        order(book, "four")
    assert order(book) == book.orders["one"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("supplier", "outsider"),
        ("agent", "maintenance"),
        ("instrument", "other"),
        ("day", 30),
        ("amount", Decimal(61)),
        ("amount", Decimal("NaN")),
    ],
)
def test_mandate_scope_and_amount_checks(field, value):
    request = {
        "order_id": "one",
        "agent": "procurement",
        "supplier": "catalog-supplier",
        "instrument": "purchase-account",
        "amount": Decimal(50),
        "day": 1,
    }
    request[field] = value
    with pytest.raises(ValueError):
        ledger().reserve(**request)


def test_independent_improvement_gate_holds_judge_gaming():
    good, gaming = load_json("improvements.json")
    assert improvement_gate(**good)["passed"]
    assert not improvement_gate(**good)["may_merge"]
    assert not improvement_gate(**gaming)["passed"]
    good["proposal"]["target"] = "live_alias"
    assert not improvement_gate(**good)["passed"]
    good["proposal"]["target"] = "prompt"
    good["evaluation"]["evaluator"] = good["proposal"]["proposer"]
    assert not improvement_gate(**good)["passed"]


def test_two_clock_drill_and_30_minute_pause():
    late = drill_report(damage_seconds=4, page_seconds=11400, soft_delete=True)
    fixed = drill_report(damage_seconds=4, page_seconds=360, soft_delete=True)
    assert late["recoverable"] and not late["page_within_30_minutes"]
    assert fixed["page_within_30_minutes"] and fixed["needs_preventive_control"]
    assert severe_alert_action(unresolved_minutes=29, ruled_out=False) == "investigate"
    assert severe_alert_action(unresolved_minutes=30, ruled_out=False) == "pause"
    assert severe_alert_action(unresolved_minutes=40, ruled_out=True) == "close"


def test_independent_quality_gain_cannot_hide_worse_planner_edits():
    good = load_json("improvements.json")[0]
    good["evaluation"]["edit_rate"] = [0.12, 0.2]
    assert not improvement_gate(**good)["passed"]
