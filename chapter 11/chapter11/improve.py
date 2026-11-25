"""The gate in front of a fix the agent proposed for itself."""

from __future__ import annotations

PROTECTED = ("evals/", "graders/", "policy/", "telemetry/", ".github/")


def review(proposal: dict) -> list[str]:
    """Return the reasons to hold a proposed change. None means it may merge."""
    before, after = proposal["before"], proposal["after"]
    reasons = []
    for path in proposal["touches"]:
        if path.startswith(PROTECTED):
            reasons.append(f"{path}: the loop may read this and never write it")
    if proposal["approver"] in (None, proposal["proposer"]):
        reasons.append("needs an approver who is not the proposer")
    for suite in ("golden", "held_out"):
        if after[suite] < before[suite]:
            reasons.append(f"{suite} set got worse")
    judge_up = after["judge"] > before["judge"]
    if judge_up and after["held_out"] <= before["held_out"]:
        reasons.append("the judge likes it more and the held-out set does not")
    longer = after["draft_words"] > 1.1 * before["draft_words"]
    if longer and after["edit_rate"] >= before["edit_rate"]:
        reasons.append("drafts got longer and planners edit them just as much")
    return reasons


def must_pause(minutes_open: int, ruled_out: bool, limit: int = 30) -> bool:
    """A severe alert nobody has ruled out within the limit pauses the agent."""
    return not ruled_out and minutes_open >= limit
