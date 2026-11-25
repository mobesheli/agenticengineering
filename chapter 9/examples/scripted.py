"""Scripted model replies with scripted usage, so the examples run without a key.

The runner, the tools, the meter, the budget, the guardrail, and the ledger are
real. Only the model's replies and the token counts it reports are fixed in
advance, which is what makes every dollar figure in the chapter reproducible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agents.testing import ScriptedModel, assistant_message, function_call
from agents.testing.model import ModelStep

from chapter9.meter import usage_of

MACHINE = "press-07"
TAGS = {"plant": "plant-2", "severity": "routine", "principal": "planner:okafor"}
DIAGNOSIS = {
    "machine_id": MACHINE,
    "fault": "main drive bearing wear",
    "parts": ["BRG-6204"],
    "confidence": "high",
}
ORDER = {
    "machine_id": MACHINE,
    "fault": "main drive bearing wear",
    "parts": ["BRG-6204"],
    "window": "next planned stop, about six hours",
    "steps": ["lock out the press", "check shaft runout", "replace BRG-6204"],
}
SENSORS = function_call(
    "read_sensor_summary", {"machine_id": MACHINE}, call_id="c1"
)
HISTORY = function_call(
    "read_repair_history", {"machine_id": MACHINE}, call_id="c2"
)
MANUAL = {"query": "press-07 main bearing replacement"}


def parts(call_id: str) -> Any:
    return function_call(
        "check_parts", {"part_number": "BRG-6204"}, call_id=call_id
    )


def step(output: list[Any], *usage: int, **details: int) -> ModelStep:
    return ModelStep(output=output, usage=usage_of(*usage, **details))


def say(payload: dict) -> list[Any]:
    return [assistant_message(json.dumps(payload))]


def frontier_run() -> tuple[ScriptedModel, ScriptedModel]:
    """Every step on the frontier model, nothing cached, one repeated call."""
    diagnose = ScriptedModel(
        [
            step([SENSORS, HISTORY], 8_000, 2_400, reasoning=1_800),
            step([parts("c3")], 14_000, 600, reasoning=300),
            step([parts("c4")], 15_000, 500, reasoning=250),
            step(
                [function_call("search_manual", MANUAL, call_id="c5")],
                16_000,
                500,
            ),
            step(say(DIAGNOSIS), 19_000, 800, reasoning=500),
        ]
    )
    draft = ScriptedModel([step(say(ORDER), 10_000, 1_200, reasoning=300)])
    return diagnose, draft


def routed_run() -> tuple[ScriptedModel, ScriptedModel, ScriptedModel]:
    """The same work with a cached prefix, and each step on the model chosen for it."""
    plan = ScriptedModel(
        [step([SENSORS, HISTORY], 8_000, 2_400, cached=6_000, reasoning=1_800)]
    )
    read = ScriptedModel(
        [
            step([parts("c3")], 14_000, 600, cached=10_000, written=2_000),
            step(
                [function_call("search_manual", MANUAL, call_id="c5")],
                16_000,
                500,
                cached=14_000,
            ),
            step(say(DIAGNOSIS), 19_000, 800, cached=16_000, reasoning=300),
        ]
    )
    draft = ScriptedModel([step(say(ORDER), 10_000, 1_200, cached=8_000)])
    return plan, read, draft


def stuck_run() -> tuple[ScriptedModel, ScriptedModel]:
    """A model that keeps asking the parts catalog the same question."""
    again = [
        step([parts(f"c{n}")], 15_000, 500, reasoning=250) for n in range(4, 12)
    ]
    diagnose = ScriptedModel(
        [
            step([SENSORS, HISTORY], 8_000, 2_400, reasoning=1_800),
            step([parts("c3")], 14_000, 600, reasoning=300),
            *again,
        ]
    )
    return diagnose, ScriptedModel([step(say(ORDER), 10_000, 1_200)])


@dataclass
class Reply:
    status: str
    task_id: str
    server: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class NordBolt:
    """A stand-in for the supplier's quoting agent from Chapter 6."""

    name = "nordbolt"

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send(self, task: dict, headers: dict[str, str]) -> Reply:
        self.calls.append(headers)
        if len(self.calls) == 1:
            return Reply("retry", "task-8841")
        return Reply(
            "completed",
            "task-8841",
            {"name": "NordBolt quoting agent", "version": "2.3.1"},
            {"cost_usd": 0.04, "receipt_id": "nb-rcpt-55120"},
        )
