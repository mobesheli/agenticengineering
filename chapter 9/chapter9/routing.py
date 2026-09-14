"""Per-step token shares and cost-quality frontier decisions."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .models import RoutingCandidate, TraceRecord

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES_PATH = ROOT / "data" / "routing" / "candidates_v1.json"


def load_candidates(path: Path = CANDIDATES_PATH) -> list[RoutingCandidate]:
    return [
        RoutingCandidate.model_validate(row)
        for row in json.loads(path.read_text(encoding="utf-8"))
    ]


def token_share_by_step(runs: Sequence[TraceRecord]) -> dict[str, dict[str, Any]]:
    totals: dict[tuple[str, str], dict[str, float | int]] = defaultdict(
        lambda: {"reasoning": 0, "output": 0, "input": 0, "cost": 0.0, "calls": 0}
    )
    for run in runs:
        for span in run.spans:
            if span.kind != "generation" or not span.usage or not span.model:
                continue
            key = (span.step_type or "unknown", span.model)
            row = totals[key]
            row["reasoning"] = int(row["reasoning"]) + span.usage.reasoning_tokens
            row["output"] = int(row["output"]) + span.usage.output_tokens
            row["input"] = int(row["input"]) + span.usage.input_tokens
            row["cost"] = float(row["cost"]) + span.cost_usd
            row["calls"] = int(row["calls"]) + 1
    grand = sum(float(row["cost"]) for row in totals.values()) or 1.0
    ordered = sorted(totals.items(), key=lambda item: -float(item[1]["cost"]))
    return {
        f"{step}/{model}": {
            **row,
            "cost": round(float(row["cost"]), 4),
            "cost_share": round(float(row["cost"]) / grand, 4),
        }
        for (step, model), row in ordered
    }


def pareto_frontier(candidates: Sequence[RoutingCandidate]) -> list[RoutingCandidate]:
    """Return configurations not beaten on both cost and quality."""

    frontier = []
    for candidate in candidates:
        dominated = any(
            other.name != candidate.name
            and other.cost_per_outcome_usd <= candidate.cost_per_outcome_usd
            and other.quality >= candidate.quality
            and (
                other.cost_per_outcome_usd < candidate.cost_per_outcome_usd
                or other.quality > candidate.quality
            )
            for other in candidates
        )
        if not dominated:
            frontier.append(candidate)
    return sorted(frontier, key=lambda item: item.cost_per_outcome_usd)


def choose_cheapest_acceptable(
    candidates: Sequence[RoutingCandidate],
    *,
    quality_floor: float,
) -> RoutingCandidate:
    eligible = [
        candidate for candidate in candidates if candidate.quality >= quality_floor
    ]
    if not eligible:
        raise ValueError("no routing configuration clears the quality floor")
    return min(eligible, key=lambda item: item.cost_per_outcome_usd)


def routing_change_gate(
    old: RoutingCandidate,
    new: RoutingCandidate,
    *,
    quality_floor: float,
    quality_margin: float = 0.0,
) -> dict[str, Any]:
    quality_ok = new.quality - quality_margin >= quality_floor
    cheaper = new.cost_per_outcome_usd < old.cost_per_outcome_usd
    return {
        "status": "accept" if quality_ok and cheaper else "reject",
        "quality_ok": quality_ok,
        "cheaper": cheaper,
        "quality_change": round(new.quality - old.quality, 4),
        "cost_change_usd": round(
            new.cost_per_outcome_usd - old.cost_per_outcome_usd, 2
        ),
        "cost_change_percent": round(
            (new.cost_per_outcome_usd / old.cost_per_outcome_usd - 1) * 100,
            2,
        ),
    }
