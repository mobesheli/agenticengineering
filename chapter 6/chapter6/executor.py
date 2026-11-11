"""The bridge: run the agent, then translate how the run ended into a task state."""

from __future__ import annotations

import logging
from datetime import date

from a2a.helpers import (
    get_data_parts,
    new_data_part,
    new_task_from_user_message,
    new_text_message,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState
from agents import Agent, Runner
from agents.exceptions import InputGuardrailTripwireTriggered, MaxTurnsExceeded

from .border import (
    BorderRejected,
    admit_quote_request,
    requested_skill,
    structured_payload,
)
from .card import JSON_MODE
from .contracts import ORDER_SKILL, QUOTE_SKILL, BillOfMaterials, FastenerQuote
from .ledger import ReplayConflict, SupplierLedger

MAX_TURNS = 6
log = logging.getLogger(__name__)


class QuotingExecutor(AgentExecutor):
    def __init__(self, agent: Agent, ledger: SupplierLedger | None = None) -> None:
        self.agent = agent
        self.ledger = ledger or SupplierLedger()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        task = context.current_task or new_task_from_user_message(message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()

        try:
            replayed = self.ledger.replay(
                message.message_id, get_data_parts(message.parts)
            )
            if replayed is not None:
                await self._finish(updater, replayed, replayed=True)
            elif task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED:
                await self._resume_quote(updater, context)
            elif requested_skill(message) == QUOTE_SKILL:
                await self._quote(updater, context, admit_quote_request(message))
            elif requested_skill(message) == ORDER_SKILL:
                await self._accept_order(updater, context)
            else:
                raise BorderRejected(
                    "the requested skill is not advertised on the card"
                )
        except (BorderRejected, ReplayConflict) as refusal:
            await updater.reject(new_text_message(f"Rejected at the border: {refusal}"))

    async def _quote(
        self, updater: TaskUpdater, context: RequestContext, bom: BillOfMaterials
    ) -> None:
        missing = bom.lines_missing_drawing()
        if missing:
            self.ledger.parked[updater.task_id] = bom
            question = f"Which drawing revision applies to {', '.join(missing)}?"
            await updater.requires_input(new_text_message(question))
            return
        try:
            run = await Runner.run(
                self.agent, input=bom.model_dump_json(), max_turns=MAX_TURNS
            )
            quote = FastenerQuote.model_validate(run.final_output)
        except InputGuardrailTripwireTriggered:
            await updater.reject(new_text_message("Request is outside quotable scope."))
            return
        except MaxTurnsExceeded:
            await updater.failed(new_text_message("Turn budget ran out on this order."))
            return
        except Exception:
            log.exception("quote run failed")
            await updater.failed(new_text_message("The quote could not be produced."))
            return
        self.ledger.quotes[quote.quote_id] = quote
        result = quote.model_dump(mode="json")
        self.ledger.remember(
            context.message.message_id, get_data_parts(context.message.parts), result
        )
        await self._finish(updater, result)

    async def _resume_quote(
        self, updater: TaskUpdater, context: RequestContext
    ) -> None:
        bom = self.ledger.parked.pop(updater.task_id, None)
        if bom is None:
            raise BorderRejected("this task is not waiting for an answer")
        answer = structured_payload(context.message)
        for line in bom.line_items:
            if line.custom and not line.drawing_rev:
                line.drawing_rev = str(answer.get("drawing_rev", ""))[:8] or None
        await self._quote(updater, context, bom)

    async def _accept_order(
        self, updater: TaskUpdater, context: RequestContext
    ) -> None:
        order = structured_payload(context.message)
        try:
            confirmation = self.ledger.accept_order(order, today=date.today())
        except (KeyError, ValueError) as problem:
            raise BorderRejected(str(problem)) from problem
        result = confirmation.model_dump(mode="json")
        self.ledger.remember(context.message.message_id, [order], result)
        await self._finish(updater, result)

    async def _finish(
        self, updater: TaskUpdater, result: dict, replayed: bool = False
    ) -> None:
        name = "order-confirmation" if "confirmation" in result else "fastener-quote"
        await updater.add_artifact(
            [new_data_part(result, media_type=JSON_MODE)],
            name=name,
            metadata={"replayed": replayed},
        )
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task
        self.ledger.parked.pop(task.id, None)
        await TaskUpdater(event_queue, task.id, task.context_id).cancel()
