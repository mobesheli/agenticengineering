"""The gap sheet for a bought agent: what the vendor provides and what it does not."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Status = Literal[
    "met", "contract", "compensating_control", "risk_acceptance", "disqualifying"
]

ENFORCED_AT_HIGH_TIER = {"identification", "audit_records", "action_limits"}


class Gap(BaseModel):
    status: Status
    note: str
    accepted_by: str | None = None


class GapSheet(BaseModel):
    agent: str
    tier: str
    requirements: dict[str, Gap]


def blocking_gaps(sheet: GapSheet) -> list[str]:
    """The gaps that stop a listing. A promise cannot stand in for every control."""
    blocking = []
    for name, gap in sheet.requirements.items():
        promise_only = gap.status == "contract" and name in ENFORCED_AT_HIGH_TIER
        if gap.status == "disqualifying":
            blocking.append(f"{name}: disqualifying for tier {sheet.tier}")
        elif promise_only and sheet.tier == "high":
            blocking.append(f"{name}: a contract line is not a control at this tier")
        elif gap.status == "risk_acceptance" and not gap.accepted_by:
            blocking.append(f"{name}: nobody has accepted this risk by name")
    return blocking
