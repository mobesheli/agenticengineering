"""Responsible-AI controls for actions that affect people."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

from .models import FairnessReport


def four_fifths_check(
    outcomes: Iterable[tuple[str, bool]],
    *,
    threshold: float = 0.8,
) -> FairnessReport:
    totals: Counter[str] = Counter()
    favorable: Counter[str] = Counter()
    for group, outcome in outcomes:
        totals[group] += 1
        favorable[group] += int(outcome)
    if not totals:
        raise ValueError("at least one outcome is required")
    rates = {
        group: favorable[group] / count
        for group, count in sorted(totals.items())
        if count
    }
    best = max(rates.values())
    ratio = min(rates.values()) / best if best else 1.0
    return FairnessReport(
        outcome_rates=rates,
        selection_ratio=ratio,
        threshold=threshold,
        passes=ratio >= threshold,
    )


class DisclosureMiddleware:
    def __init__(self, disclosure: str = "You are interacting with an AI agent.") -> None:
        self.disclosure = disclosure
        self._seen_channels: set[str] = set()

    def first_turn(self, channel_id: str, message: str) -> str:
        if channel_id in self._seen_channels:
            return message
        self._seen_channels.add(channel_id)
        return f"{self.disclosure}\n\n{message}"


def outcome_rates_by_group(
    outcomes: Iterable[tuple[str, bool]],
) -> dict[str, tuple[int, int]]:
    counts: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for group, outcome in outcomes:
        counts[group][0] += int(outcome)
        counts[group][1] += 1
    return {group: tuple(values) for group, values in sorted(counts.items())}
