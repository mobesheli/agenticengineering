"""Human approval as a route: pause the run, store it, and resume on a decision."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from agents import Agent, RunContextWrapper, Runner, RunResult, function_tool
from agents.run_state import RunState
from pydantic import BaseModel

from chapter5.models import MODELS

RELEASE_LIMIT_CENTS = 500_000
APPROVAL_WINDOW = timedelta(hours=4)
RELEASED: dict[str, int] = {}


async def above_release_limit(
    ctx: RunContextWrapper, params: dict[str, Any], call_id: str
) -> bool:
    return params["amount_cents"] > RELEASE_LIMIT_CENTS


@function_tool(needs_approval=above_release_limit)
async def release_payment(payment_id: str, amount_cents: int) -> str:
    """Release a held payment to the beneficiary."""
    RELEASED[payment_id] = amount_cents
    return f"released {payment_id}"


payments_agent = Agent(
    name="payments_agent",
    model=MODELS.mid,
    instructions="Release the payment the operator names. Report what happened.",
    tools=[release_payment],
)


class PaymentCase(BaseModel):
    case_id: str
    request: str
    evidence: list[str]


class CaseStatus(BaseModel):
    case_id: str
    state: Literal["awaiting_approval", "closed", "on_hold"]
    outcome: str = ""


class ApprovalStore:
    """Pending approvals in a database: the paused run, the evidence, the deadline."""

    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS pending ("
            "case_id TEXT PRIMARY KEY, run_state TEXT, evidence TEXT, expires_at TEXT)"
        )

    def save(self, case: PaymentCase, run_state: str, now: datetime) -> None:
        expires = (now + APPROVAL_WINDOW).isoformat()
        self.db.execute(
            "INSERT OR REPLACE INTO pending VALUES (?, ?, ?, ?)",
            (case.case_id, run_state, "\n".join(case.evidence), expires),
        )
        self.db.commit()

    def take(self, case_id: str) -> str:
        row = self.db.execute(
            "SELECT run_state FROM pending WHERE case_id = ?", (case_id,)
        ).fetchone()
        self.db.execute("DELETE FROM pending WHERE case_id = ?", (case_id,))
        self.db.commit()
        return row[0]

    def overdue(self, now: datetime) -> list[str]:
        rows = self.db.execute(
            "SELECT case_id FROM pending WHERE expires_at < ?", (now.isoformat(),)
        )
        return [case_id for (case_id,) in rows]


def closed(case_id: str, result: RunResult) -> CaseStatus:
    return CaseStatus(case_id=case_id, state="closed", outcome=result.final_output)


async def advance_payment(case: PaymentCase, pending: ApprovalStore) -> CaseStatus:
    result = await Runner.run(payments_agent, case.request, max_turns=4)
    if result.interruptions:
        run_state = result.to_state().to_string()
        pending.save(case, run_state, datetime.now(UTC))
        return CaseStatus(case_id=case.case_id, state="awaiting_approval")
    return closed(case.case_id, result)


async def resume_payment(
    case_id: str, approved: bool, note: str, pending: ApprovalStore
) -> CaseStatus:
    state = await RunState.from_string(payments_agent, pending.take(case_id))
    for request in state.get_interruptions():
        if approved:
            state.approve(request)
        else:
            state.reject(request, rejection_message=note)
    result = await Runner.run(payments_agent, state, max_turns=4)
    return closed(case_id, result)


async def hold_overdue(pending: ApprovalStore, now: datetime) -> list[CaseStatus]:
    """Silence is not consent: an unanswered request is rejected and held."""
    note = "No reviewer answered in time. Payment stays on hold."
    held = []
    for case_id in pending.overdue(now):
        status = await resume_payment(case_id, False, note, pending)
        held.append(status.model_copy(update={"state": "on_hold"}))
    return held
