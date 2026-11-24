"""Intake: decide whether to reuse, buy, or build before anybody builds anything."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class Brief(BaseModel):
    name: str
    purpose: str
    audience: str
    reviewer: str
    data_tier: Literal["low", "medium", "high"]
    capabilities: list[str]
    company_specific: bool


class Recommendation(BaseModel):
    route: Literal["reuse", "buy", "build"]
    reason: str
    scaffold: dict[str, Any] | None = None


def best_match(
    brief: Brief, offers: list[dict[str, Any]]
) -> tuple[dict[str, Any], float]:
    wanted = set(brief.capabilities)
    scored = [
        (offer, len(wanted & set(offer["capabilities"])) / len(wanted))
        for offer in offers
    ]
    return max(scored, key=lambda pair: pair[1])


def recommend(
    brief: Brief, marketplace: list[dict[str, Any]], vendors: list[dict[str, Any]]
) -> Recommendation:
    agent, overlap = best_match(brief, marketplace)
    if overlap >= 0.75:
        reason = f"{agent['agent']} already covers {overlap:.0%} of this"
        return Recommendation(route="reuse", reason=reason)
    product, covered = best_match(brief, vendors)
    if covered >= 0.75 and not brief.company_specific:
        reason = f"{product['product']} is licensed and covers {covered:.0%}"
        return Recommendation(route="buy", reason=reason)
    scaffold = {
        "route": "assemble",
        "tier": brief.data_tier,
        "identity": f"agent-{brief.name}",
        "budget": {"monthly_usd": 100, "source": "metered"},
        "gate_mode": "monitor",
        "golden_suite": [],
    }
    return Recommendation(
        route="build", reason="nothing existing fits", scaffold=scaffold
    )
