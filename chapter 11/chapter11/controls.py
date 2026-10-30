"""Local demonstrations of mandates, independent gates, and the two stop clocks."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from .models import Record


class Mandate(Record):
    mandate_id: str
    agent: str
    authorized_by: str = Field(min_length=1)
    instrument: str = Field(min_length=1)
    suppliers: list[str] = Field(min_length=1)
    transaction_cap: Decimal = Field(gt=0)
    daily_cap: Decimal = Field(gt=0)
    expires_day: int = Field(gt=0)
    revoked: bool = False


class MandateLedger:
    """Single-process teaching ledger; no payment provider is contacted."""

    def __init__(self, mandate: Mandate):
        self.mandate = mandate.model_copy(deep=True)
        self.orders: dict[str, dict] = {}

    def reserve(
        self,
        *,
        order_id: str,
        agent: str,
        supplier: str,
        instrument: str,
        amount: Decimal,
        day: int,
    ) -> dict:
        amount = Decimal(amount)
        request = {
            "agent": agent,
            "supplier": supplier,
            "instrument": instrument,
            "amount": str(amount),
            "day": day,
        }
        if order_id in self.orders:
            if self.orders[order_id] != request:
                raise ValueError("idempotency key reused for a different order")
            return dict(self.orders[order_id])
        m = self.mandate
        if m.revoked or not 0 <= day < m.expires_day:
            raise ValueError("mandate is revoked or expired")
        if (
            agent != m.agent
            or supplier not in m.suppliers
            or instrument != m.instrument
        ):
            raise ValueError("order is outside the mandate scope")
        if not amount.is_finite() or amount <= 0 or amount > m.transaction_cap:
            raise ValueError("transaction amount is outside the cap")
        spent = sum(
            (Decimal(o["amount"]) for o in self.orders.values() if o["day"] == day),
            Decimal(0),
        )
        if spent + amount > m.daily_cap:
            raise ValueError("daily cap exceeded")
        self.orders[order_id] = request
        return dict(request)

    def revoke(self) -> dict:
        self.mandate.revoked = True
        return {
            "revoked": True,
            "in_flight_orders": sorted(self.orders),
            "next_step": "review cancellation or compensation for each existing order",
        }


def improvement_gate(proposal: dict, evaluation: dict) -> dict:
    """Only a trusted evaluator supplies this report; the proposer cannot approve."""
    reasons = []
    allowed = {"prompt", "tool_description", "retrieval", "route"}
    if proposal["target"] not in allowed:
        reasons.append(
            "proposer cannot write graders, criteria, audit logs, or live aliases"
        )
    if proposal["proposer"] == evaluation["evaluator"]:
        reasons.append("proposer cannot grade its own change")
    if evaluation["proposal_id"] != proposal["proposal_id"]:
        reasons.append("evaluation belongs to another proposal")
    for suite in ("replay", "golden", "held_out"):
        before, after = evaluation[suite]
        if not (0 <= before <= after <= 1):
            reasons.append(f"{suite} regressed or has invalid scores")
    if evaluation["held_out_visible_to_proposer"]:
        reasons.append("held-out cases were exposed to the proposer")
    edit_before, edit_after = evaluation["edit_rate"]
    if not (0 <= edit_after <= edit_before <= 1):
        reasons.append("planner edit rate regressed or has invalid scores")
    # A judge gain alone does not establish benefit on independent outcomes.
    if (
        evaluation["held_out"][1] <= evaluation["held_out"][0]
        and evaluation["edit_rate"][1] >= evaluation["edit_rate"][0]
    ):
        reasons.append("no independent improvement; investigate judge gaming")
    return {
        "candidate": proposal["proposal_id"],
        "passed": not reasons,
        "reasons": reasons,
        "may_merge": False,
        "next_step": "named human approval" if not reasons else "hold",
    }


def drill_report(
    *, damage_seconds: int, page_seconds: int | None, soft_delete: bool
) -> dict:
    if damage_seconds < 0 or (page_seconds is not None and page_seconds < 0):
        raise ValueError("clock values must be nonnegative")
    return {
        "damage_seconds": damage_seconds,
        "page_seconds": page_seconds,
        "fast_control": "48-hour soft delete" if soft_delete else "none",
        "recoverable": soft_delete,
        "page_within_30_minutes": page_seconds is not None and page_seconds <= 1800,
        "needs_preventive_control": page_seconds is None
        or damage_seconds < page_seconds,
    }


def severe_alert_action(*, unresolved_minutes: int, ruled_out: bool) -> str:
    if unresolved_minutes < 0:
        raise ValueError("elapsed time cannot be negative")
    return (
        "pause"
        if unresolved_minutes >= 30 and not ruled_out
        else "investigate"
        if not ruled_out
        else "close"
    )
