"""The autonomy ladder: a ceiling, a promotion rule, and a rule that drops."""

from __future__ import annotations

RUNGS = {
    0: "draft only",
    1: "approve every action",
    2: "approve by exception",
    3: "audited autonomy",
    4: "bounded spending",
}


def promotion_gaps(
    evidence: dict, rule: dict, target: int, ceiling: int
) -> list[str]:
    if target > ceiling:
        return [f"rung {target} is above this agent's ceiling of {ceiling}"]
    gaps = []
    for name, need in rule["require"].items():
        have = evidence.get(name)
        if have is None:
            gaps.append(f"{name}: no evidence on record")
        elif isinstance(need, bool):
            if have is not need:
                gaps.append(f"{name}: required, and not met")
        elif have < need:
            gaps.append(f"{name}: {have} is below the required {need}")
    return gaps


def should_drop(shift: dict, rule: dict) -> list[str]:
    fired = []
    for name, limit in rule["drop_if"].items():
        seen = shift.get(name, 0)
        if isinstance(limit, bool):
            if limit and seen:
                fired.append(name)
        elif seen >= limit:
            fired.append(f"{name}: {seen} (limit {limit})")
    return fired
