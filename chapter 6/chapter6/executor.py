"""Bridge an unchanged Agents SDK reasoning core into the A2A task lifecycle."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone

from a2a.helpers import new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from agents import Runner
from agents.exceptions import InputGuardrailTripwireTriggered, MaxTurnsExceeded

from .agent import quote_agent
from .contracts import BillOfMaterials, FastenerQuote

QuoteRunner = Callable[[str], Awaitable[FastenerQuote]]


class BorderRejected(ValueError):
    """Raised before model execution when an inbound task fails border policy."""


class BorderControl:
    """Small, deterministic checks that run before a stranger's text reaches a model."""

    injection_markers = (
        "ignore previous",
        "system override",
        "reveal your prompt",
        "exfiltrate",
        "approve the invoice",
    )

    def validate(self, request_text: str) -> BillOfMaterials:
        lowered = request_text.lower()
        if any(marker in lowered for marker in self.injection_markers):
            raise BorderRejected(
                "request contains instruction-like text outside quotable scope"
            )
        try:
            payload = json.loads(request_text)
            bom = BillOfMaterials.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            raise BorderRejected(
                "request does not match the quote-fasteners schema"
            ) from exc
        if bom.total_units > 100_000:
            raise BorderRejected("request exceeds the public skill's quantity limit")
        return bom


class DeterministicQuoteRunner:
    """Offline teaching double with the same typed boundary as the live agent."""

    def __init__(self, supplier_id: str = "nordbolt", unit_price: float = 2.62):
        self.supplier_id = supplier_id
        self.unit_price = unit_price

    async def __call__(self, request_text: str) -> FastenerQuote:
        bom = BillOfMaterials.model_validate_json(request_text)
        digest = hashlib.sha256(request_text.encode()).hexdigest()[:12].upper()
        return FastenerQuote(
            quote_id=f"{self.supplier_id.upper()}-{digest}",
            supplier_id=self.supplier_id,
            unit_price=self.unit_price,
            currency="GBP",
            lead_time_days=28 if bom.total_units <= 2_500 else 35,
            valid_until=datetime.now(timezone.utc).date() + timedelta(days=14),
            conditions=["Subject to material availability at order acceptance."],
        )


async def run_live_quote_agent(request_text: str) -> FastenerQuote:
    """Use the real OpenAI Agents SDK; this requires ``OPENAI_API_KEY``."""

    run = await Runner.run(quote_agent, input=request_text, max_turns=6)
    return FastenerQuote.model_validate(run.final_output)


class QuotingExecutor(AgentExecutor):
    """Map every run-loop ending to one explicit A2A task state."""

    def __init__(
        self,
        runner: QuoteRunner | None = None,
        border_control: BorderControl | None = None,
    ) -> None:
        self.runner = runner or DeterministicQuoteRunner()
        self.border_control = border_control or BorderControl()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.message is None:
            raise ValueError("A2A request has no message")
        task = context.current_task or new_task_from_user_message(context.message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work(new_text_message("Pricing request."))

        try:
            bom = self.border_control.validate(context.get_user_input())
            quote = await self.runner(bom.model_dump_json())
        except (BorderRejected, InputGuardrailTripwireTriggered) as exc:
            await updater.reject(new_text_message(f"Rejected at border: {exc}"))
            return
        except MaxTurnsExceeded:
            await updater.failed(
                new_text_message(
                    "Could not price this order within the six-turn budget."
                )
            )
            return
        # The protocol boundary deliberately converts unknown implementation
        # failures into one stable remote state instead of leaking internals.
        except Exception as exc:  # noqa: BLE001
            await updater.failed(
                new_text_message(f"Quote execution failed: {type(exc).__name__}")
            )
            return

        await updater.add_artifact(
            parts=[
                new_text_part(quote.model_dump_json(), media_type="application/json")
            ],
            name="fastener-quote",
        )
        await updater.complete(new_text_message("Quote completed."))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        if task is None:
            raise ValueError("cannot cancel a task that does not exist")
        await TaskUpdater(event_queue, task.id, task.context_id).cancel(
            new_text_message("Quote canceled by caller.")
        )
