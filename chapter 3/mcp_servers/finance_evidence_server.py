"""A finance evidence server: one read-only tool and one resource.

Run it from the chapter directory and leave it running in its own terminal:

    python mcp_servers/finance_evidence_server.py

It listens on http://127.0.0.1:8765/mcp over Streamable HTTP. The ledger is a
small in-memory stand-in so the server has something true to say.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Account:
    """One line of the chart of accounts."""

    code: str
    name: str
    kind: str


@dataclass
class FakeLedger:
    """A general ledger with one entity, two quarters, and six accounts."""

    accounts: list[Account] = field(
        default_factory=lambda: [
            Account("1000", "Cash and cash equivalents", "asset"),
            Account("1200", "Trade receivables", "asset"),
            Account("2000", "Trade payables", "liability"),
            Account("2400", "Short-term borrowings", "liability"),
            Account("4000", "Revenue", "income"),
            Account("6000", "Operating expenses", "expense"),
        ]
    )
    balances: dict[tuple[str, str], dict[str, int]] = field(
        default_factory=lambda: {
            ("UK01", "2026-Q2"): {
                "1000": 4_820_000, "1200": 1_310_500, "2000": -965_200,
                "2400": -2_500_000, "4000": -7_240_000, "6000": 4_574_700,
            },
            ("UK01", "2026-Q3"): {
                "1000": 5_104_300, "1200": 1_488_900, "2000": -1_020_750,
                "2400": -2_500_000, "4000": -7_915_000, "6000": 4_842_550,
            },
        }
    )

    def snapshot(self, *, period: str, entity: str, materiality_threshold: int) -> dict:
        """Return balances for one period and entity above a materiality threshold."""
        rows = self.balances.get((entity, period))
        if rows is None:
            return {"ok": False, "error_class": "not_found", "retryable": False,
                    "user_safe_message": "No trial balance exists for that entity and period.",
                    "machine_action_hint": "ask_user"}
        names = {account.code: account.name for account in self.accounts}
        lines = [
            {"account": code, "name": names[code], "balance": balance}
            for code, balance in sorted(rows.items())
            if abs(balance) >= materiality_threshold
        ]
        return {"ok": True, "entity": entity, "period": period,
                "materiality_threshold": materiality_threshold,
                "source_ref": f"tb:{entity}:{period}", "lines": lines}

    def account_dictionary_yaml(self) -> str:
        """Render the chart of accounts as YAML."""
        out = ["accounts:"]
        for account in self.accounts:
            out.append(f"  - code: \"{account.code}\"")
            out.append(f"    name: {account.name}")
            out.append(f"    kind: {account.kind}")
        return "\n".join(out) + "\n"


ledger = FakeLedger()

app = MCPServer("finance-evidence")

class TrialBalanceQuery(BaseModel):
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    entity: str = Field(min_length=2)
    materiality_threshold: int = Field(ge=0)

@app.tool()
def get_trial_balance_snapshot(query: TrialBalanceQuery) -> dict:
    """Return a trial balance snapshot for the named period and entity,
    filtered to accounts above the materiality threshold.
    Read-only. Safe to call repeatedly."""
    return ledger.snapshot(**query.model_dump())

@app.resource("schema://accounts")
def accounts_schema() -> str:
    """The chart of accounts as YAML, for the host to read directly."""
    return ledger.account_dictionary_yaml()

if __name__ == "__main__":
    app.run(transport="streamable-http", host="127.0.0.1", port=8765)
