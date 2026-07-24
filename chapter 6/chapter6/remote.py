"""Remote-agent adapters with idempotency, timeouts, and stable error shapes."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest, TaskState

from .audit import audit_log
from .card import demo_signature_verifier
from .contracts import BillOfMaterials, FastenerQuote, QuoteToolResult, TaskOutcome
from .registry import COUNTERPARTIES, CircuitOpenError, CounterpartyRegistry


class RemoteTaskHandle:
    def __init__(self, outcome: TaskOutcome):
        self.outcome = outcome

    async def wait_terminal(self, timeout_seconds: float) -> TaskOutcome:
        del timeout_seconds
        await asyncio.sleep(0)
        return self.outcome


class ScriptedSupplierClient:
    """Deterministic remote agent used by the notebook and offline tests."""

    def __init__(
        self,
        supplier_id: str,
        unit_price: float,
        lead_time_days: int,
        scripted_states: Iterable[str] = (),
    ) -> None:
        self.supplier_id = supplier_id
        self.unit_price = unit_price
        self.lead_time_days = lead_time_days
        self.scripted_states = list(scripted_states)
        self.idempotency_cache: dict[str, TaskOutcome] = {}
        self.calls = 0

    async def send_task(
        self, *, skill: str, payload: str, idempotency_key: str
    ) -> RemoteTaskHandle:
        if idempotency_key in self.idempotency_cache:
            return RemoteTaskHandle(self.idempotency_cache[idempotency_key])
        self.calls += 1
        task_id = f"task-{self.supplier_id}-{self.calls}"
        if self.scripted_states:
            state = self.scripted_states.pop(0)
            if state != "completed":
                outcome = TaskOutcome(
                    task_id=task_id,
                    state=state,
                    reason=f"scripted {state}",
                )
                self.idempotency_cache[idempotency_key] = outcome
                return RemoteTaskHandle(outcome)

        if skill == "quote-fasteners":
            bom = BillOfMaterials.model_validate_json(payload)
            digest = hashlib.sha256(payload.encode()).hexdigest()[:10].upper()
            quote = FastenerQuote(
                quote_id=f"{self.supplier_id.upper()}-{digest}",
                supplier_id=self.supplier_id,
                unit_price=self.unit_price,
                currency="GBP",
                lead_time_days=self.lead_time_days,
                valid_until=datetime.now(timezone.utc).date() + timedelta(days=14),
                conditions=[f"Capacity checked for {bom.total_units} units."],
            )
            artifacts: list[dict[str, Any]] = [quote.model_dump(mode="json")]
        elif skill == "accept-order":
            po = json.loads(payload)
            artifacts = [{"confirmation": f"CONF-{po['po_number']}", "accepted": True}]
        else:
            outcome = TaskOutcome(
                task_id=task_id,
                state="rejected",
                reason=f"skill not advertised: {skill}",
            )
            self.idempotency_cache[idempotency_key] = outcome
            return RemoteTaskHandle(outcome)

        outcome = TaskOutcome(task_id=task_id, state="completed", artifacts=artifacts)
        self.idempotency_cache[idempotency_key] = outcome
        return RemoteTaskHandle(outcome)


def mint_idempotency_key(action: str, supplier_id: str, payload: str) -> str:
    canonical = f"{action}\0{supplier_id}\0{payload}".encode()
    return hashlib.sha256(canonical).hexdigest()


def parse_quote(artifacts: list[dict[str, Any]]) -> FastenerQuote:
    if not artifacts:
        raise ValueError("completed quote task returned no artifact")
    return FastenerQuote.model_validate(artifacts[0])


async def request_supplier_quote(
    supplier_id: str,
    bom_json: str,
    *,
    registry: CounterpartyRegistry | None = None,
) -> QuoteToolResult:
    """Request a priced quote from one allowlisted supplier agent."""

    registry = registry or COUNTERPARTIES
    entry = registry.require(supplier_id)
    try:
        entry.breaker.before_call()
    except CircuitOpenError:
        return QuoteToolResult(
            ok=False, error_class="supplier_circuit_open", retryable=False
        )

    try:
        task = await entry.client().send_task(
            skill="quote-fasteners",
            payload=bom_json,
            idempotency_key=mint_idempotency_key("quote", supplier_id, bom_json),
        )
        outcome = await asyncio.wait_for(
            task.wait_terminal(timeout_seconds=entry.sla_seconds),
            timeout=entry.sla_seconds,
        )
    except TimeoutError:
        entry.breaker.record_failure()
        return QuoteToolResult(ok=False, error_class="supplier_timeout", retryable=True)
    # A remote transport can fail through several backend-specific exception
    # types; callers receive one stable tool error contract.
    except Exception as exc:  # noqa: BLE001
        entry.breaker.record_failure()
        return QuoteToolResult(
            ok=False,
            error_class=f"supplier_transport_{type(exc).__name__}",
            retryable=True,
        )

    await audit_log.record_exchange(
        event_type="quote",
        entry=entry,
        request_payload=bom_json,
        outcome=outcome,
        identity="procurement-agent/on-behalf-of/demo-buyer",
    )
    if outcome.state != "completed":
        if outcome.state == "failed":
            entry.breaker.record_failure()
        return QuoteToolResult(
            ok=False,
            error_class=f"supplier_{outcome.state}",
            retryable=outcome.state == "failed",
        )

    try:
        quote = parse_quote(outcome.artifacts)
    except ValueError:
        entry.breaker.record_failure()
        return QuoteToolResult(
            ok=False, error_class="supplier_invalid_artifact", retryable=False
        )
    entry.breaker.record_success()
    return QuoteToolResult(ok=True, quote=quote)


class A2AQuoteClient:
    """Small adapter over the official A2A 1.x client used by the server test."""

    def __init__(
        self,
        base_url: str,
        *,
        httpx_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.httpx_client = httpx_client

    async def send_task(
        self, *, skill: str, payload: str, idempotency_key: str
    ) -> RemoteTaskHandle:
        owns_client = self.httpx_client is None
        http_client = self.httpx_client or httpx.AsyncClient()
        try:
            card = await A2ACardResolver(http_client, self.base_url).get_agent_card()
            verifier = demo_signature_verifier()
            verifier(card)
            client = await create_client(
                agent=card,
                client_config=ClientConfig(streaming=False, httpx_client=http_client),
                signature_verifier=verifier,
            )
            message = new_text_message(payload, role=Role.ROLE_USER)
            request = SendMessageRequest(
                message=message,
                metadata={"skill": skill, "idempotencyKey": idempotency_key},
            )
            task_proto = None
            async for response in client.send_message(request):
                if response.HasField("task"):
                    task_proto = response.task
            if task_proto is None:
                raise RuntimeError("A2A response did not contain a task")
            state = (
                TaskState.Name(task_proto.status.state)
                .removeprefix("TASK_STATE_")
                .lower()
            )
            artifacts: list[dict[str, Any]] = []
            for artifact in task_proto.artifacts:
                for part in artifact.parts:
                    if part.HasField("text"):
                        artifacts.append(json.loads(part.text))
            reason = (
                task_proto.status.message.parts[0].text
                if task_proto.status.message.parts
                else None
            )
            return RemoteTaskHandle(
                TaskOutcome(
                    task_id=task_proto.id,
                    state=state,
                    artifacts=artifacts,
                    reason=reason,
                )
            )
        finally:
            if owns_client:
                await http_client.aclose()
