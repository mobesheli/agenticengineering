from __future__ import annotations

import json

import pytest

from chapter6.registry import (
    CircuitBreaker,
    CircuitOpenError,
    CounterpartyEntry,
    CounterpartyRegistry,
)
from chapter6.remote import ScriptedSupplierClient, request_supplier_quote


def make_bom(suffix: int = 0) -> str:
    return json.dumps(
        {
            "commodity": "industrial-fasteners",
            "requested_delivery_date": "2026-09-01",
            "line_items": [
                {
                    "sku": f"BOLT-{suffix}",
                    "description": "stainless bolt",
                    "quantity": 100 + suffix,
                }
            ],
        }
    )


def make_registry(client: ScriptedSupplierClient) -> CounterpartyRegistry:
    registry = CounterpartyRegistry()
    registry.register(
        CounterpartyEntry(
            id="nordbolt",
            display_name="NordBolt",
            commodity_codes={"industrial-fasteners"},
            client_factory=lambda: client,
            card_version="1.0.0",
            contract_reference="MSA-NB-2026",
            approved_by="security-board",
        )
    )
    return registry


@pytest.mark.asyncio
async def test_failed_is_retryable_rejected_is_not() -> None:
    failed_client = ScriptedSupplierClient(
        "nordbolt", 2.62, 28, scripted_states=["failed"]
    )
    failed = await request_supplier_quote(
        "nordbolt", make_bom(), registry=make_registry(failed_client)
    )
    assert failed.error_class == "supplier_failed"
    assert failed.retryable is True

    rejected_client = ScriptedSupplierClient(
        "nordbolt", 2.62, 28, scripted_states=["rejected"]
    )
    rejected = await request_supplier_quote(
        "nordbolt", make_bom(), registry=make_registry(rejected_client)
    )
    assert rejected.error_class == "supplier_rejected"
    assert rejected.retryable is False


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_three_remote_failures() -> None:
    client = ScriptedSupplierClient(
        "nordbolt", 2.62, 28, scripted_states=["failed", "failed", "failed"]
    )
    registry = make_registry(client)
    for index in range(3):
        result = await request_supplier_quote(
            "nordbolt", make_bom(index), registry=registry
        )
        assert result.retryable is True

    blocked = await request_supplier_quote("nordbolt", make_bom(4), registry=registry)
    assert blocked.error_class == "supplier_circuit_open"
    assert client.calls == 3
    assert registry.require("nordbolt").breaker.state == "open"


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_same_remote_task() -> None:
    client = ScriptedSupplierClient("nordbolt", 2.62, 28)
    first = await client.send_task(
        skill="quote-fasteners", payload=make_bom(), idempotency_key="same-intent"
    )
    second = await client.send_task(
        skill="quote-fasteners", payload=make_bom(), idempotency_key="same-intent"
    )
    assert first.outcome.task_id == second.outcome.task_id
    assert client.calls == 1


def test_open_circuit_moves_half_open_then_closes_after_probe() -> None:
    now = [100.0]
    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout_seconds=10,
        clock=lambda: now[0],
    )
    for _ in range(3):
        breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        breaker.before_call()

    now[0] = 111.0
    breaker.before_call()
    assert breaker.state == "half_open"
    breaker.record_success()
    assert breaker.state == "closed"
