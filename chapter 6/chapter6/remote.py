"""Calling a remote agent: verify first, then delegate, wait, and translate."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, create_client
from a2a.helpers import get_data_parts, get_message_text, new_data_message
from a2a.types import Role, SendMessageRequest, Task, TaskState
from a2a.utils.signing import SignatureVerificationError
from pydantic import ValidationError

from .audit import audit_log
from .card import JSON_MODE, card_fingerprint
from .contracts import QUOTE_SKILL, FastenerQuote, QuoteToolResult, TaskOutcome
from .ledger import content_hash
from .registry import (
    COUNTERPARTIES,
    CircuitOpenError,
    CounterpartyEntry,
    CounterpartyRegistry,
)


class CardChanged(RuntimeError):
    """The card on the wire is not the card that was approved."""


@dataclass
class Delegation:
    """What a call across the boundary needs, and a model must never choose."""

    http: httpx.AsyncClient
    authorized_by: str
    case_id: str
    registry: CounterpartyRegistry = COUNTERPARTIES


def mint_idempotency_key(
    action: str, supplier_id: str, case_id: str, payload: Any
) -> str:
    return f"{action}-{content_hash([supplier_id, case_id, payload])[:24]}"


async def connect(entry: CounterpartyEntry, http: httpx.AsyncClient) -> Client:
    resolver = A2ACardResolver(http, entry.trust.agent_url)
    card = await resolver.get_agent_card(signature_verifier=entry.trust.verifier())
    if card_fingerprint(card) != entry.trust.card_fingerprint:
        raise CardChanged(f"card {card.version} is not the card that was approved")
    config = ClientConfig(streaming=False, httpx_client=http)
    return await create_client(card, config)


def to_outcome(task: Task) -> TaskOutcome:
    state = TaskState.Name(task.status.state).removeprefix("TASK_STATE_").lower()
    artifacts = [data for a in task.artifacts for data in get_data_parts(a.parts)]
    reason = get_message_text(task.status.message) or None
    return TaskOutcome(task_id=task.id, state=state, artifacts=artifacts, reason=reason)


async def send_task(
    entry: CounterpartyEntry,
    http: httpx.AsyncClient,
    skill: str,
    payload: dict[str, Any],
    idempotency_key: str,
    task_id: str | None = None,
) -> TaskOutcome:
    client = await connect(entry, http)
    message = new_data_message(payload, JSON_MODE, task_id=task_id, role=Role.ROLE_USER)
    message.message_id = idempotency_key
    message.metadata.update({"skill": skill})
    request = SendMessageRequest(message=message)
    if entry.webhook is not None:
        request.configuration.task_push_notification_config.CopyFrom(entry.webhook)
    task = None
    async for event in client.send_message(request):
        if event.HasField("task"):
            task = event.task
    if task is None:
        raise RuntimeError("the remote agent answered without a task")
    return to_outcome(task)


def refusal(supplier_id: str, error_class: str, **details: Any) -> QuoteToolResult:
    return QuoteToolResult(
        ok=False, supplier_id=supplier_id, error_class=error_class, **details
    )


def quote_result(entry: CounterpartyEntry, outcome: TaskOutcome) -> QuoteToolResult:
    if outcome.state == "failed":
        entry.breaker.record_failure()
    if outcome.state != "completed":
        return refusal(
            entry.id,
            f"supplier_{outcome.state}",
            retryable=outcome.state == "failed",
            detail=outcome.reason,
            task_id=outcome.task_id,
        )
    try:
        quote = FastenerQuote.model_validate(outcome.artifacts[0])
    except (IndexError, ValidationError):
        entry.breaker.record_failure()
        return refusal(entry.id, "supplier_invalid_artifact", task_id=outcome.task_id)
    entry.breaker.record_success()
    return QuoteToolResult(
        ok=True, supplier_id=entry.id, quote=quote, task_id=outcome.task_id
    )


async def request_supplier_quote(
    via: Delegation, supplier_id: str, bom: dict[str, Any]
) -> QuoteToolResult:
    """Request a priced quote for a bill of materials from an approved supplier."""
    entry = via.registry.require(supplier_id)
    key = mint_idempotency_key("quote", supplier_id, via.case_id, bom)
    try:
        entry.breaker.before_call()
        outcome = await asyncio.wait_for(
            send_task(entry, via.http, QUOTE_SKILL, bom, key), entry.sla_seconds
        )
    except CircuitOpenError:
        return refusal(supplier_id, "supplier_circuit_open")
    except (SignatureVerificationError, CardChanged) as untrusted:
        return refusal(supplier_id, "supplier_untrusted_card", detail=str(untrusted))
    except TimeoutError:
        entry.breaker.record_failure()
        return refusal(supplier_id, "supplier_timeout", retryable=True)
    except Exception as broken:
        entry.breaker.record_failure()
        problem = type(broken).__name__
        return refusal(
            supplier_id, "supplier_unreachable", retryable=True, detail=problem
        )
    audit_log.record("quote", entry, via.authorized_by, key, bom, outcome)
    return quote_result(entry, outcome)


async def answer_supplier_question(
    via: Delegation, supplier_id: str, task_id: str, answer: dict[str, Any]
) -> QuoteToolResult:
    """Send the missing input to a parked task and collect the quote."""
    entry = via.registry.require(supplier_id)
    key = mint_idempotency_key("answer", supplier_id, via.case_id, [task_id, answer])
    outcome = await asyncio.wait_for(
        send_task(entry, via.http, QUOTE_SKILL, answer, key, task_id), entry.sla_seconds
    )
    audit_log.record("answer", entry, via.authorized_by, key, answer, outcome)
    return quote_result(entry, outcome)
