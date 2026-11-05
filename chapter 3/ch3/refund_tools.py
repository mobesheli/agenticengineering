"""Refund tools built across the side-effect boundary.

The model fills in the business request. The orchestration layer fills in the
idempotency key and the actor through the run context. ``issue_refund`` is safe
to retry; ``execute_refund`` is the same action behind an approval gate whose
policy is a function of the arguments, so small refunds flow and large ones stop.
"""

from __future__ import annotations

from typing import Annotated, Literal

from agents import RunContextWrapper, function_tool
from pydantic import BaseModel, Field

from ch3 import payments
from ch3.deps import RunDeps


class RefundRequest(BaseModel):
    customer_id: str
    original_charge_id: str
    amount_cents: int = Field(gt=0)
    reason: str = Field(max_length=200)


class RefundResult(BaseModel):
    status: Literal["issued", "replayed"]
    refund_id: str
    amount_cents: int


@function_tool
def issue_refund(ctx: RunContextWrapper[RunDeps], req: RefundRequest) -> RefundResult:
    """Issue a refund against a previously authorized charge. Safe to
    retry: a repeated request returns the original refund."""
    row = payments.create_refund_atomic(
        idempotency_key=ctx.context.idempotency_key,
        charge_id=req.original_charge_id,
        amount_cents=req.amount_cents,
        actor_id=ctx.context.actor_id,
        reason=req.reason,
    )
    return RefundResult(status="replayed" if row.replayed else "issued",
                        refund_id=row.refund_id, amount_cents=row.amount_cents)


def issue_refund_impl(deps: RunDeps, req: RefundRequest) -> RefundResult:
    """The refund write without the tool wrapper, shared by the gated tool.

    Same statement, same store, same replay semantics as ``issue_refund``.
    """
    row = payments.create_refund_atomic(
        idempotency_key=deps.idempotency_key,
        charge_id=req.original_charge_id,
        amount_cents=req.amount_cents,
        actor_id=deps.actor_id,
        reason=req.reason,
    )
    return RefundResult(status="replayed" if row.replayed else "issued",
                        refund_id=row.refund_id, amount_cents=row.amount_cents)


# The gated tool takes its fields flat on purpose. The pinned SDK consults an
# approval policy only when every parameter is a plain JSON value. Give the tool
# a nested Pydantic model and every call is routed to approval without the
# policy being asked, which is the safe way to fail and not the behavior wanted.

async def needs_second_pair_of_eyes(
    ctx: RunContextWrapper[RunDeps], args: dict, call_id: str
) -> bool:
    return args["amount_cents"] > 10_000     # above $100: a human


@function_tool(needs_approval=needs_second_pair_of_eyes)
def execute_refund(
    ctx: RunContextWrapper[RunDeps],
    customer_id: str,
    original_charge_id: str,
    amount_cents: Annotated[int, Field(gt=0)],
    reason: Annotated[str, Field(max_length=200)],
) -> RefundResult:
    """Execute a previously previewed refund. Large refunds pause for
    approval; the approver sees the previewed amount and reason."""
    req = RefundRequest(customer_id=customer_id, original_charge_id=original_charge_id,
                        amount_cents=amount_cents, reason=reason)
    return issue_refund_impl(ctx.context, req)
