"""The investigator: a model-led loop with read-only tools and a typed result."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from agents import Agent, function_tool
from pydantic import BaseModel

from chapter5.models import DEEP, MODELS

CASES = json.loads((Path(__file__).parent.parent / "data" / "cases.json").read_text())

INVESTIGATION_GUIDE = """You investigate one anti-money-laundering alert.
Use the tools to read the customer's profile, recent transactions, earlier
cases, and the watchlist. Compare the alerted activity with what is usual for
this customer. Recommend "clear" only when the activity matches an established
pattern and nothing touches the watchlist. Otherwise recommend "escalate". In
evidence, list only the identifiers of the records you relied on, one per item,
such as txn-1234, and put your reasoning in rationale. You never close a case
yourself."""


class CaseAssessment(BaseModel):
    recommendation: Literal["clear", "escalate"]
    evidence: list[str]
    rationale: str


class InvestigationResult(BaseModel):
    case_id: str
    status: Literal["concluded", "escalated_to_human", "retry_queued"]
    reason: str
    assessment: CaseAssessment | None = None


@function_tool
def get_customer_profile(customer_id: str) -> dict:
    """Read the customer's profile and usual activity."""
    return CASES["customers"].get(customer_id, {"error": "unknown customer"})


@function_tool
def get_transactions(customer_id: str) -> list[dict]:
    """Read the customer's recent transactions, newest first."""
    return CASES["transactions"].get(customer_id, [])


@function_tool
def recall_case_history(customer_id: str) -> list[str]:
    """Read how earlier alerts on this customer were resolved."""
    return CASES["case_history"].get(customer_id, [])


@function_tool
def screen_counterparty(name: str) -> dict:
    """Check a counterparty name against the watchlist."""
    return {"name": name, "listed": name in CASES["watchlist"]}


READ_ONLY_TOOLS = [
    get_customer_profile,
    get_transactions,
    recall_case_history,
    screen_counterparty,
]

investigator = Agent(
    name="alert_investigator",
    model=MODELS.frontier,
    model_settings=DEEP,
    instructions=INVESTIGATION_GUIDE,
    tools=READ_ONLY_TOOLS,
    output_type=CaseAssessment,
)
