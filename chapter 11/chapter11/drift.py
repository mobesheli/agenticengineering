"""Five drift decisions, with effective configuration checked before metrics."""

from enum import Enum

from .models import SIGNALS, Reading, RunConfiguration


class Decision(str, Enum):
    OK = "ok"
    HOLD = "hold"
    RERUN = "rerun"
    PROPOSE = "propose"
    BUDGET = "budget_event"


def configuration_changes(
    pinned: RunConfiguration, effective: RunConfiguration
) -> list[str]:
    return [
        key
        for key, value in pinned.model_dump().items()
        if effective.model_dump()[key] != value
    ]


def decide(readings: list[Reading], config_matches_bundle: bool) -> Decision:
    """Missing or duplicate signals hold; a zero baseline uses an absolute band."""
    if not config_matches_bundle:
        return Decision.HOLD
    if len(readings) != len(SIGNALS) or {r.signal for r in readings} != set(SIGNALS):
        return Decision.HOLD
    moved = {r.signal: r.value - r.baseline for r in readings if r.moved}
    if not moved:
        return Decision.OK
    if "cost_speed" in moved:
        return Decision.BUDGET
    if set(moved) == {"outcome"} and moved["outcome"] > 0:
        return Decision.PROPOSE
    return Decision.RERUN


def fallback_drill(primary: str, secondary: dict, suite: str) -> dict:
    """Switch a simulated route only when its uncached evidence clears the floor."""
    eligible = (
        secondary["suite"] == suite
        and secondary["model"] != primary
        and not secondary["cached"]
        and 0 <= secondary["floor"] <= secondary["pass_rate"] <= 1
    )
    return {
        "primary_disabled": True,
        "route": secondary["model"] if eligible else None,
        "status": "degraded" if eligible else "paused",
        "quality": secondary["pass_rate"] if eligible else None,
        "planners_notified": True,
    }
