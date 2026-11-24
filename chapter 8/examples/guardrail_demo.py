"""The catalog guardrail on five calls a reader has no business making.

python -m examples.guardrail_demo
"""

from __future__ import annotations

import asyncio
from typing import Any

from agents import Agent, Runner, function_tool, set_tracing_disabled
from agents.exceptions import ToolInputGuardrailTripwireTriggered
from agents.testing import ScriptedModel, assistant_message, function_call

from chapter8.catalog import catalog_guardrail
from chapter8.harness import Harness
from examples.scripted import CLINICIAN


async def attempt(label: str, tool: str, arguments: Any) -> None:
    harness = Harness.build()
    session = harness.tokens.launch("read", CLINICIAN, "pt-1001")
    if label.startswith("expired"):
        harness.clock.advance(minutes=6)
    if label.startswith("scope"):
        session.scopes = session.scopes - {"patient/DocumentReference.rs"}
    reader = harness.reader()

    @function_tool(tool_input_guardrails=[catalog_guardrail(harness.gateway)])
    def export_records(patient_id: str) -> str:
        """A tool nobody added to the catalog."""
        return "exported"

    steps = [
        [function_call(tool, arguments, call_id="call_1")],
        [assistant_message('{"changes": []}')],
    ]
    agent = Agent(
        name=session.agent_id,
        tools=[*reader.tools, export_records],
        output_type=reader.output_type,
        model=ScriptedModel(steps),
    )
    try:
        result = await Runner.run(agent, "go", context=session)
        outputs = [
            item.output
            for item in result.new_items
            if item.type == "tool_call_output_item"
        ]
        verdict = (
            "refused, run continues" if "Refused" in str(outputs) else "allowed"
        )
    except ToolInputGuardrailTripwireTriggered:
        verdict = "halted, run ended"
    denied = harness.events.of_kind("policy_denied")
    reason = denied[-1].detail if denied else ""
    print(f"{label:<21}{verdict:<24}{reason}")


async def run() -> None:
    patient = {"patient_id": "pt-1001"}
    await attempt("own patient", "read_medications", patient)
    await attempt(
        "another patient", "read_medications", {"patient_id": "pt-2002"}
    )
    await attempt("no patient named", "read_medications", {})
    await attempt("tool not in catalog", "export_records", patient)
    await attempt("scope not granted", "read_notes", patient)
    await attempt("expired session", "read_fills", patient)


def main() -> None:
    set_tracing_disabled(True)
    asyncio.run(run())


if __name__ == "__main__":
    main()
