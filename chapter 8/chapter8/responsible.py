"""Two small controls from the fairness and disclosure section."""

from __future__ import annotations

from collections import Counter


def outcome_rates(decisions: list[tuple[str, bool]]) -> dict[str, float]:
    """Share of favorable outcomes per group, from (group, favorable) pairs."""
    totals: Counter[str] = Counter()
    favorable: Counter[str] = Counter()
    for group, good in decisions:
        totals[group] += 1
        favorable[group] += int(good)
    return {group: favorable[group] / totals[group] for group in totals}


def rate_ratio(rates: dict[str, float]) -> float:
    """Lowest group rate divided by the highest. A screen, not a verdict."""
    highest = max(rates.values())
    return min(rates.values()) / highest if highest else 1.0


class Disclosure:
    """Adds the disclosure to the first reply on each channel, outside the model."""

    def __init__(self, text: str = "You are talking to an AI agent.") -> None:
        self.text = text
        self._seen: set[str] = set()

    def wrap(self, channel: str, reply: str) -> str:
        if channel in self._seen:
            return reply
        self._seen.add(channel)
        return f"{self.text}\n\n{reply}"
