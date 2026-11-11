from __future__ import annotations

import asyncio
from datetime import date, timedelta

import httpx
import pytest

from chapter6.audit import audit_log
from chapter6.card import build_card, sign_card
from chapter6.contracts import Approval
from chapter6.neighborhood import NORDBOLT
from chapter6.procurement import (
    commit_purchase_order,
    compare_quotes,
    gather_quotes,
    propose_order,
)
from chapter6.registry import COUNTERPARTIES, CircuitBreaker, CircuitOpenError
from chapter6.remote import Delegation, answer_supplier_question, request_supplier_quote
from chapter6.sample import BUYER, CASE, NEEDED_IN_DAYS, bracket_bom


async def quote(hood, supplier="nordbolt", bom=None):
    return await request_supplier_quote(
        Delegation(hood.http, BUYER, CASE), supplier, bom or bracket_bom()
    )


async def approved_order(hood, po_number="PO-1"):
    quoted = await quote(hood)
    po = propose_order(
        po_number,
        "nordbolt",
        quoted.quote,
        2000,
        date.today() + timedelta(days=NEEDED_IN_DAYS),
    )
    approval = Approval(
        reference="APR-1",
        approved_by="a.okafor",
        po_number=po.po_number,
        maximum_amount=po.total_value,
        expires_on=quoted.quote.valid_until,
    )
    return po, approval


async def test_parked_task_resumes_on_the_same_task(hood):
    parked = await quote(hood, bom=bracket_bom(drawing_rev=None))
    assert parked.error_class == "supplier_input_required" and "CB-42" in parked.detail
    resumed = await answer_supplier_question(
        Delegation(hood.http, BUYER, CASE),
        "nordbolt",
        parked.task_id,
        {"drawing_rev": "C"},
    )
    assert resumed.ok and resumed.task_id == parked.task_id


async def test_repeated_quote_request_returns_the_same_quote_without_a_second_run(hood):
    first = await quote(hood)
    calls_after_first = len(hood["nordbolt"].model.calls)
    second = await quote(hood)
    assert second.quote == first.quote
    assert len(hood["nordbolt"].model.calls) == calls_after_first


async def test_a_new_sourcing_case_gets_a_new_key_and_a_fresh_quote(hood):
    await quote(hood)
    calls_after_first = len(hood["nordbolt"].model.calls)
    other_case = Delegation(hood.http, BUYER, "SR-2292")
    again = await request_supplier_quote(other_case, "nordbolt", bracket_bom())
    assert again.ok and len(hood["nordbolt"].model.calls) > calls_after_first


async def test_commit_is_idempotent_and_conflicts_are_refused(hood):
    po, approval = await approved_order(hood)
    first = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE), po, approval
    )
    second = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE), po, approval
    )
    assert first.committed and second.confirmation == first.confirmation
    changed = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE),
        po.model_copy(update={"quantity": 1500}),
        approval,
    )
    assert not changed.committed and "different content" in changed.reason
    assert len(hood["nordbolt"].ledger.orders) == 1


async def test_approval_covers_one_order_at_one_price_until_it_expires(hood):
    po, approval = await approved_order(hood)
    bigger = po.model_copy(update={"quantity": 2500})
    other = po.model_copy(update={"po_number": "PO-2"})
    expired = approval.model_copy(
        update={"expires_on": date.today() - timedelta(days=1)}
    )
    for order, grant in ((bigger, approval), (other, approval), (po, expired)):
        result = await commit_purchase_order(
            Delegation(hood.http, BUYER, CASE), order, grant
        )
        assert (
            not result.committed
            and result.reason == "approval_does_not_cover_this_order"
        )
    assert not hood["nordbolt"].ledger.orders


async def test_supplier_refuses_an_order_it_did_not_quote(hood):
    po, approval = await approved_order(hood)
    forged = po.model_copy(update={"unit_price": 1.00})
    grant = approval.model_copy(update={"maximum_amount": 10_000})
    result = await commit_purchase_order(
        Delegation(hood.http, BUYER, CASE), forged, grant
    )
    assert not result.committed and "does not match the quoted price" in result.reason


async def test_audit_records_intent_before_outcome(hood):
    po, approval = await approved_order(hood)
    await commit_purchase_order(Delegation(hood.http, BUYER, CASE), po, approval)
    events = [e.event for e in audit_log.events]
    assert events == ["quote", "commit_intent", "commit_outcome"]
    intent, outcome = audit_log.events[1:]
    assert intent.state is None and outcome.state == "completed"
    assert intent.request_hash == outcome.request_hash
    assert outcome.authorized_by == "buyer/a.okafor"


async def test_lost_commit_leaves_an_intent_and_the_retry_places_one_order(hood):
    po, approval = await approved_order(hood)
    via = Delegation(hood.http, BUYER, CASE)
    hood["nordbolt"].transport.online = False
    lost = await commit_purchase_order(via, po, approval)
    assert not lost.committed and lost.reason.startswith("outcome_unknown")
    assert [e.event for e in audit_log.events][-1] == "commit_intent"
    hood["nordbolt"].transport.online = True
    retried = await commit_purchase_order(via, po, approval)
    assert retried.committed and len(hood["nordbolt"].ledger.orders) == 1


async def test_breaker_opens_after_three_failures_and_fan_out_survives(hood):
    hood["nordbolt"].transport.online = False
    classes = [(await quote(hood)).error_class for _ in range(4)]
    assert classes == ["supplier_unreachable"] * 3 + ["supplier_circuit_open"]
    results = await gather_quotes(
        Delegation(hood.http, BUYER, CASE), bracket_bom(), "custom-brackets"
    )
    by_supplier = {r.supplier_id: r for r in results}
    assert by_supplier["rivetridge"].ok and not by_supplier["nordbolt"].ok
    assert compare_quotes(results, NEEDED_IN_DAYS).supplier_id == "rivetridge"


def test_breaker_half_opens_after_the_recovery_window():
    now = [0.0]
    breaker = CircuitBreaker(
        failure_threshold=2, recovery_seconds=10, clock=lambda: now[0]
    )
    breaker.record_failure()
    breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        breaker.before_call()
    now[0] = 11
    breaker.before_call()
    assert breaker.state == "half_open"
    breaker.record_failure()
    assert breaker.state == "open"
    now[0] = 30
    breaker.before_call()
    breaker.record_success()
    assert breaker.state == "closed"


async def test_slow_supplier_times_out_at_the_registry_sla(hood):
    class Slow(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            await asyncio.sleep(1)
            raise httpx.ConnectError("never mind", request=request)

    COUNTERPARTIES.require("nordbolt").sla_seconds = 0.05
    slow_http = httpx.AsyncClient(transport=Slow())
    result = await request_supplier_quote(
        Delegation(slow_http, BUYER, CASE), "nordbolt", bracket_bom()
    )
    await slow_http.aclose()
    assert result.error_class == "supplier_timeout" and result.retryable


async def test_unknown_key_and_changed_card_are_not_trusted(hood):
    def card(**changes):
        return build_card(
            name="nordbolt-quoting-agent",
            organization=NORDBOLT.organization,
            base_url=NORDBOLT.base_url,
            **changes,
        )

    hood.serve("nordbolt", sign_card(card(), "impostor"))
    assert (await quote(hood)).error_class == "supplier_untrusted_card"

    hood.serve("nordbolt", sign_card(card(version="1.5.0"), "nordbolt-2026-01"))
    result = await quote(hood)
    assert result.error_class == "supplier_untrusted_card"
    assert "not the card that was approved" in result.detail
    assert COUNTERPARTIES.require("nordbolt").breaker.failures == 0


def test_comparison_is_plain_code():
    from chapter6.contracts import FastenerQuote, QuoteToolResult

    def result(supplier, price, days):
        q = FastenerQuote(
            quote_id=supplier,
            unit_price=price,
            currency="GBP",
            lead_time_days=days,
            valid_until=date.today(),
        )
        return QuoteToolResult(ok=True, supplier_id=supplier, quote=q)

    results = [result("a", 3.00, 60), result("b", 3.20, 30), result("c", 3.10, 40)]
    assert compare_quotes(results, needed_in_days=42).supplier_id == "c"
    with pytest.raises(ValueError):
        compare_quotes(results, needed_in_days=10)
