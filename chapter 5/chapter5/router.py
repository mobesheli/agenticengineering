"""A classifier router: the model sorts, the code acts, and "other" goes to a person."""

from __future__ import annotations

from typing import Literal

from agents import Agent, Runner
from pydantic import BaseModel

from chapter5.models import MODELS, QUICK

Category = Literal["balance_inquiry", "dispute", "fraud_report", "other"]

CATEGORY_GUIDE = """Sort one customer request into exactly one category.

balance_inquiry: the customer wants to know a balance, a limit, or whether a
payment has arrived. Example: "Has my salary come in yet?" Not this: "There is
a payment here I never made", which is fraud_report.

dispute: the customer made a payment and disagrees with it, such as a double
charge or goods that never arrived. Example: "The hotel charged me twice." Not
this: a payment the customer says they never made, which is fraud_report.

fraud_report: the customer does not recognize a payment, has lost a card, or
thinks someone else has access. Example: "I have never heard of this shop."

other: anything else, and anything you are unsure about.

Report your confidence between 0 and 1, and give the reason in one sentence."""


class DispatchOutcome(BaseModel):
    category: Category
    handled_by: Literal["specialist", "human"]
    output: str


SPECIALISTS = {
    "balance_inquiry": Agent(
        name="balance_agent",
        model=MODELS.small,
        instructions="Answer balance and payment-status questions.",
    ),
    "dispute": Agent(
        name="dispute_agent",
        model=MODELS.frontier,
        instructions="Open a dispute case and explain the next steps.",
    ),
    "fraud_report": Agent(
        name="fraud_agent",
        model=MODELS.frontier,
        instructions="Secure the account and open a fraud case.",
    ),
}
HUMAN_QUEUE: list[tuple[str, RouteDecision]] = []


async def enqueue_for_human(request: str, decision: RouteDecision) -> DispatchOutcome:
    HUMAN_QUEUE.append((request, decision))
    return DispatchOutcome(
        category=decision.category, handled_by="human", output="Queued for a person."
    )


ESCALATE_BELOW = 0.70


class RouteDecision(BaseModel):
    category: Category
    confidence: float
    reason: str


request_router = Agent(
    name="request_router",
    model=MODELS.small,
    model_settings=QUICK,
    instructions=CATEGORY_GUIDE,
    output_type=RouteDecision,
)


async def dispatch(request: str) -> DispatchOutcome:
    routing = await Runner.run(request_router, request, max_turns=1)
    decision = routing.final_output
    if decision.category == "other" or decision.confidence < ESCALATE_BELOW:
        return await enqueue_for_human(request, decision)
    specialist = SPECIALISTS[decision.category]
    reply = (await Runner.run(specialist, request)).final_output
    return DispatchOutcome(
        category=decision.category, handled_by="specialist", output=reply
    )
