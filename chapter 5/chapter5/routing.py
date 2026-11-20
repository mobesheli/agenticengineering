"""Two ways for one agent to use another: a handoff, or a tool call."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from agents import Agent, RunContextWrapper, function_tool, handoff
from agents.extensions import handoff_filters
from pydantic import BaseModel

from chapter5.models import MODELS

INTAKE_GUIDE = """You are the first point of contact for a bank's customers.
Answer nothing yourself except fee questions, which you answer with the
estimate_fees tool. Transfer account and policy questions to faq_agent.
Transfer anything about a transaction the customer does not recognize or
disagrees with to dispute_specialist, and say why in the transfer."""

FEE_SCHEDULE = {"standard": (Decimal("0.30"), 100), "premium": (Decimal("0.10"), 500)}
TRANSFERS: list[TransferReason] = []


class TransferReason(BaseModel):
    reason: str
    transaction_reference: str


async def record_transfer(ctx: RunContextWrapper, why: TransferReason) -> None:
    TRANSFERS.append(why)


@function_tool
def estimate_fees(tier: Literal["standard", "premium"], payments: int) -> str:
    """Work out monthly payment fees for an account tier and a number of payments."""
    per_payment, free_payments = FEE_SCHEDULE[tier]
    billable = max(payments - free_payments, 0)
    fee = billable * per_payment
    return f"{billable} billable payments at {per_payment} each: {fee}"


faq_agent = Agent(
    name="faq_agent",
    model=MODELS.small,
    instructions="Answer common account and policy questions concisely.",
)
dispute_specialist = Agent(
    name="dispute_specialist",
    model=MODELS.frontier,
    instructions="Own disputed-transaction conversations through to resolution.",
)
intake_agent = Agent(
    name="intake_agent",
    model=MODELS.mid,
    instructions=INTAKE_GUIDE,
    handoffs=[
        handoff(faq_agent, input_filter=handoff_filters.remove_all_tools),
        handoff(
            dispute_specialist, input_type=TransferReason, on_handoff=record_transfer
        ),
    ],
    tools=[estimate_fees],
)
