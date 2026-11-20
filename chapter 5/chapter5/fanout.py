"""Fan-out: independent specialists run side by side, and code merges their views."""

from __future__ import annotations

import asyncio
from typing import Literal

from agents import Agent, Runner
from pydantic import BaseModel

from chapter5.investigation import screen_counterparty
from chapter5.models import MODELS

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


class SpecialistView(BaseModel):
    source: str
    risk: Literal["low", "medium", "high"]
    evidence: list[str]
    summary: str


class CombinedView(BaseModel):
    risk: Literal["low", "medium", "high"]
    evidence: list[str]
    specialists_disagree: bool
    missing: list[str]


EVIDENCE_RULE = """In evidence, list only the identifiers of the records you
relied on, one per item, such as txn-1234. Put everything else in summary."""


def specialist(name: str, task: str, tools: list | None = None) -> Agent:
    return Agent(
        name=name,
        model=MODELS.mid,
        instructions=f"{task} {EVIDENCE_RULE} Set source to {name}.",
        tools=tools or [],
        output_type=SpecialistView,
    )


sanctions_screener = specialist(
    "sanctions_screener",
    "Check every counterparty named in the case with the screen_counterparty tool.",
    tools=[screen_counterparty],
)
transaction_pattern_analyst = specialist(
    "transaction_pattern_analyst",
    "Compare the activity with known laundering patterns.",
)
counterparty_network_mapper = specialist(
    "counterparty_network_mapper",
    "Map who the counterparties are and how they connect.",
)
SPECIALISTS = [
    sanctions_screener,
    transaction_pattern_analyst,
    counterparty_network_mapper,
]


async def gather_specialist_views(case_summary: str) -> CombinedView:
    runs = [Runner.run(agent, case_summary, max_turns=3) for agent in SPECIALISTS]
    results = await asyncio.gather(*runs, return_exceptions=True)
    views = [r.final_output for r in results if not isinstance(r, BaseException)]
    failed = [
        agent.name
        for agent, r in zip(SPECIALISTS, results, strict=True)
        if isinstance(r, BaseException)
    ]
    return merge_views(views, failed)


def merge_views(views: list[SpecialistView], missing: list[str]) -> CombinedView:
    risks = {view.risk for view in views}
    highest = max(risks, key=RISK_ORDER.get) if risks else "high"
    evidence = sorted({item for view in views for item in view.evidence})
    return CombinedView(
        risk="high" if missing else highest,
        evidence=evidence,
        specialists_disagree=len(risks) > 1,
        missing=missing,
    )
