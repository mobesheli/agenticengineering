"""Measuring a router against labels a person assigned."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class Scored:
    """One request: the label a reviewer gave it and what the router decided."""

    label: str
    predicted: str
    confidence: float


def confusion(sample: list[Scored]) -> Counter[tuple[str, str]]:
    return Counter((item.label, item.predicted) for item in sample)


def precision_recall(sample: list[Scored], category: str) -> tuple[float, float]:
    hits = sum(1 for s in sample if s.label == category and s.predicted == category)
    predicted = sum(1 for s in sample if s.predicted == category)
    actual = sum(1 for s in sample if s.label == category)
    return (hits / predicted if predicted else 0.0, hits / actual if actual else 0.0)


def threshold_report(sample: list[Scored], thresholds: list[float]) -> list[dict]:
    """For each threshold: how much goes to people, and how much is routed wrongly."""
    rows = []
    for threshold in thresholds:
        to_human = [
            s for s in sample if s.predicted == "other" or s.confidence < threshold
        ]
        automated = [s for s in sample if s not in to_human]
        wrong = sum(1 for s in automated if s.label != s.predicted)
        rows.append(
            {
                "threshold": threshold,
                "to_human": len(to_human) / len(sample),
                "misrouted": wrong / len(sample),
            }
        )
    return rows
