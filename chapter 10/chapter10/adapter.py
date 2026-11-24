"""Bring a team's existing evaluation suite to the gate without rewriting it."""

from __future__ import annotations

from typing import Any

from chapter10.gate import EvalResult


def from_team_suite(report: dict[str, Any], bundle: str) -> EvalResult:
    """Map one team's report format onto the result every gate reads.

    The team's suite records each case with a list of attempts. The gate needs the
    outcome of every attempt, because a pass rate alone cannot be compared by task.
    """
    outcomes = {
        case["name"]: [attempt["status"] == "ok" for attempt in case["attempts"]]
        for case in report["cases"]
    }
    trial_counts = {len(trials) for trials in outcomes.values()}
    if len(trial_counts) != 1:
        raise ValueError("every case must have the same number of attempts")
    return EvalResult(
        bundle=bundle,
        suite=f"{report['suite_name']}@{report['suite_revision']}",
        trials=trial_counts.pop(),
        cached=report.get("used_cache", False),
        outcomes=outcomes,
        tokens=sum(a["tokens"] for c in report["cases"] for a in c["attempts"]),
    )
