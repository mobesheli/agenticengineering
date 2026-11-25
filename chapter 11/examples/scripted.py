"""Scripted model replies, so the examples run without a key.

The runner, the agent, the structured output, and every check are real. Only the
model's replies are fixed in advance, which keeps the printed results the same on
every run. `examples/live_check.py` runs the same agent against a live model.
"""

from __future__ import annotations

import json

from agents import set_tracing_disabled
from agents.testing import ScriptedModel, assistant_message
from agents.testing.model import ModelStep


def merges(*replies: dict) -> ScriptedModel:
    set_tracing_disabled(True)
    steps = [
        ModelStep(output=[assistant_message(json.dumps(r))]) for r in replies
    ]
    return ScriptedModel(steps)


COMPRESSOR = {
    "text": "Compressor C2 is serviced every 60 days.",
    "claims": [{"name": "service_days", "value": "60"}],
    "source_ids": ["session-0090", "session-0131"],
}
