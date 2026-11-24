"""The Rule of Two as a check you can run against a design."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capabilities:
    untrusted_input: bool
    sensitive_data: bool
    state_change: bool

    def held(self) -> int:
        return sum(
            [self.untrusted_input, self.sensitive_data, self.state_change]
        )

    def verdict(self) -> str:
        if self.held() == 3:
            return "split it, or gate the action"
        return "may run unattended"


DESIGNS = {
    "one session": Capabilities(True, True, True),
    "read phase": Capabilities(True, True, False),
    "write phase": Capabilities(False, True, True),
}

AUTONOMY = {
    "read": "act",
    "reversible-write": "act within limits",
    "consequential-write": "act with approval",
    "irreversible-or-external": "act with approval",
    "changes-own-capabilities": "advise",
}


def autonomy_for(risk_tier: str) -> str:
    """The most autonomy a task may have. Unknown tiers get the least."""
    return AUTONOMY.get(risk_tier, "advise")
