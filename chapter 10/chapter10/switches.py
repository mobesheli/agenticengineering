"""Six externally owned kill switches with a drillable interface."""

from __future__ import annotations

import time

from .models import DrillResult, KillSwitch

DEFAULT_SWITCHES = (
    ("gateway", "finops-on-call", "platform-duty", "all model calls"),
    ("identity", "identity-on-call", "security-duty", "all tool and data actions"),
    ("contract", "tool-owner", "security-duty", "one operation or scope"),
    ("runtime", "runtime-on-call", "platform-duty", "new runs and queued work"),
    ("register", "governance-owner", "risk-duty", "discovery and new adoption"),
    ("data", "data-product-owner", "data-duty", "unsafe certified inputs"),
)


class KillSwitchMap:
    def __init__(self, agent: str, target: str = "all") -> None:
        self.agent = agent
        self._switches = {
            name: KillSwitch(
                name=name,
                owner=owner,
                backup=backup,
                stops=stops,
                target=target,
            )
            for name, owner, backup, stops in DEFAULT_SWITCHES
        }

    def press(self, name: str, *, target: str | None = None) -> KillSwitch:
        switch = self._switches[name]
        replacement = switch.model_copy(
            update={"active": True, "target": target or switch.target}
        )
        self._switches[name] = replacement
        return replacement

    def reset(self, name: str) -> KillSwitch:
        switch = self._switches[name].model_copy(update={"active": False})
        self._switches[name] = switch
        return switch

    def status(self) -> tuple[KillSwitch, ...]:
        return tuple(self._switches.values())

    def drill(self, name: str, *, target: str = "staging") -> DrillResult:
        started = time.perf_counter_ns()
        switch = self.press(name, target=target)
        elapsed_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
        result = DrillResult(
            switch=name,
            target=switch.target,
            active=switch.active,
            elapsed_ms=elapsed_ms,
        )
        self.reset(name)
        return result

    def drill_all(self) -> tuple[DrillResult, ...]:
        return tuple(self.drill(name) for name in self._switches)
