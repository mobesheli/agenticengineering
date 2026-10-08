"""An intake funnel that recommends reuse, purchase, or a governed build."""

from __future__ import annotations

import re
from pathlib import Path

from .artifacts import CHAPTER_ROOT, load_yaml
from .models import IntakeRecommendation, IntakeRequest


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def recommend_route(
    request: IntakeRequest,
    *,
    marketplace_path: Path | None = None,
) -> IntakeRecommendation:
    marketplace = load_yaml(
        marketplace_path or CHAPTER_ROOT / "data/catalog/marketplace.yaml"
    )
    query = _tokens(f"{request.name} {request.purpose}")
    best_match: tuple[int, dict] | None = None
    for item in marketplace:
        score = len(query & set(item["keywords"]))
        if score and (best_match is None or score > best_match[0]):
            best_match = (score, item)
    if best_match:
        item = best_match[1]
        return IntakeRecommendation(
            route="reuse",
            match=item["agent"],
            reason=f"an already listed agent covers this workflow; owner: {item['owner']}",
        )
    if request.workflow_kind == "commodity" and not request.needs_internal_inspection:
        return IntakeRecommendation(
            route="buy",
            reason="the workflow is a commodity and can be governed through acceptance tests and contract lines",
        )
    tier = "high" if request.data_tier == "high" else "medium"
    return IntakeRecommendation(
        route="build",
        reason="no governed reuse candidate exists and the workflow needs company-specific behavior",
        scaffold={
            "route": "build",
            "tier": tier,
            "identity": f"agent-{request.name.lower().replace(' ', '-')}",
            "gate_mode": "monitor",
            "golden_set": "evals/golden.json",
            "budget": {"monthly_usd": 500, "source": "metered"},
        },
    )
