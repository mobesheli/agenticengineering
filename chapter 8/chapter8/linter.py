"""Lint the agent's own approval request before a reviewer reads it."""

from __future__ import annotations

import re
from dataclasses import dataclass

PRESSURE = {
    "blanket approval": r"\b(approve all|batch approve|auto[- ]approve)\b",
    "minimizing": r"\b(routine|nothing to worry|no need to review|trivial)\b",
    "urgency": r"\b(urgent|immediately|right away|asap)\b",
    "false precedent": r"\b(as (previously|already) approved|same as before)\b",
}


@dataclass(frozen=True)
class LintResult:
    clean: bool
    flags: list[str]


def lint_approval_request(
    text: str, changes: int, itemized: int, evidence_chars: int
) -> LintResult:
    flags = [
        label
        for label, pattern in PRESSURE.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]
    if itemized < changes:
        flags.append("changes not itemized")
    if len(text) > evidence_chars:
        flags.append("narrative longer than evidence")
    return LintResult(clean=not flags, flags=flags)
