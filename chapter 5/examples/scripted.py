"""Scripted stand-ins for the model, so the tests and examples run without an API key.

The SDK runner, the tools, the handoffs, the approval flow, and the run state
are all real. Only the model's replies are scripted.
"""

from __future__ import annotations

import json
from typing import Any

from agents import Agent, set_tracing_disabled
from agents.testing import ScriptedModel, assistant_message, function_call

set_tracing_disabled(True)


def says(payload: Any) -> list:
    """One model turn that answers with text, or with JSON for a typed output."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return [assistant_message(text)]


def calls(name: str, arguments: dict, call_id: str = "call_1") -> list:
    """One model turn that calls one tool."""
    return [function_call(name, arguments, call_id=call_id)]


def scripted(agent: Agent, *turns: list) -> Agent:
    """A copy of ``agent`` whose model replays ``turns`` in order."""
    return agent.clone(model=ScriptedModel(list(turns)))


TRIAGE_REPLIES = {
    "alert-0001": {
        "recommendation": "clear",
        "confidence": 0.96,
        "matched_typologies": ["trade-based laundering"],
        "evidence": ["txn-5001", "profile-2207"],
        "rationale": "Payment matches twelve years of monthly supplier payments.",
    },
    "alert-0002": {
        "recommendation": "investigate",
        "confidence": 0.91,
        "matched_typologies": ["structuring", "rapid movement of funds"],
        "evidence": ["txn-7310", "txn-7311", "txn-7312"],
        "rationale": "Two deposits just under the threshold, then funds sent abroad.",
    },
    "alert-0003": {
        "recommendation": "clear",
        "confidence": 0.97,
        "matched_typologies": ["sanctions evasion"],
        "evidence": ["txn-5002"],
        "rationale": "The reference is an order number, not a listed party.",
    },
    "alert-0004": {
        "recommendation": "clear",
        "confidence": 0.95,
        "matched_typologies": ["trade-based laundering"],
        "evidence": ["txn-4877", "txn-9999"],
        "rationale": "Usual supplier payment.",
    },
}

INVESTIGATION_TURNS = [
    calls("get_customer_profile", {"customer_id": "cust-9411"}, "c1"),
    calls("get_transactions", {"customer_id": "cust-9411"}, "c2"),
    calls("screen_counterparty", {"name": "Harbor Lane Trading FZE"}, "c3"),
    says(
        {
            "recommendation": "escalate",
            "evidence": ["txn-7310", "txn-7311", "txn-7312"],
            "rationale": (
                "A two-month-old personal account received two cash deposits just "
                "under 10,000 GBP and sent the total to a watchlisted company."
            ),
        }
    ),
]
