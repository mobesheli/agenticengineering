"""Small stand-ins for the systems a retirement touches.

In your company these are the register repository, the trace store, the identity
directory, and the archive. The retirement script only needs the few operations
below from each, which is the point of writing it against them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Register:
    entries: dict[str, dict]
    routes: dict[str, str] = field(default_factory=dict)

    def freeze(self, agent: str, successor: str) -> dict:
        entry = self.entries[agent]
        entry.update(status="deprecated", successor=successor)
        return entry

    def redirect(self, caller: str, old: str, new: str) -> None:
        self.routes[f"{caller}->{old}"] = new

    def close(self, agent: str, obituary: dict) -> None:
        self.entries[agent].update(status="retired", obituary=obituary)


@dataclass
class Traces:
    calls: list[dict]

    def callers(self, agent: str, since: int) -> set[str]:
        return {
            c["caller"]
            for c in self.calls
            if c["agent"] == agent and c["day"] >= since
        }

    def reached(self, caller: str, agent: str) -> bool:
        return any(
            c["caller"] == caller and c["agent"] == agent and c["ok"]
            for c in self.calls
        )


@dataclass
class Identity:
    tokens: dict[str, list[dict]]
    active: set[str]
    revoked: int = 0

    def deactivate(self, agent: str) -> None:
        self.active.discard(agent)

    def revoke_tokens(self, agent: str) -> int:
        held = self.tokens.get(agent, [])
        self.tokens[agent] = [t for t in held if not t["revocable"]]
        self.revoked += len(held) - len(self.tokens[agent])
        return self.revoked

    def revoke_at_source(self, agent: str, token_id: str) -> None:
        """For a token this directory did not issue and cannot revoke itself."""
        self.tokens[agent] = [
            t for t in self.tokens[agent] if t["id"] != token_id
        ]
        self.revoked += 1

    def live_tokens(self, agent: str) -> list[str]:
        return [t["id"] for t in self.tokens.get(agent, [])]


@dataclass
class Archive:
    held: dict[str, dict] = field(default_factory=dict)

    def store(self, agent: str, entry: dict, keep_until: str) -> dict:
        kept = ["bundle", "golden_suite", "eval_history", "traces", "decisions"]
        self.held[agent] = {"keep_until": keep_until, "items": kept}
        return self.held[agent]
