"""Scripted stand-ins for the model, so the examples and tests run without an API key.

The SDK runner, the session, the tools, the MCP server, and the guardrail are all
real. Only the model's replies are scripted.
"""

from __future__ import annotations

import json

from agents import set_tracing_disabled
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call

set_tracing_disabled(True)


def tool_outputs(items) -> dict[str, str]:
    return {
        item["call_id"]: item["output"]
        if isinstance(item["output"], str)
        else json.dumps(item["output"])
        for item in items
        if not isinstance(item, str) and item.get("type") == "function_call_output"
    }


def scripted_billing_model() -> ScriptedModel:
    def first(call):
        return [assistant_message("Sorry about that. Which two charges do you mean?")]

    def second(call):
        earlier = [item for item in call.input if not isinstance(item, str)][:-1]
        said = earlier[0]["content"]
        said = said if isinstance(said, str) else said[0]["text"]
        return [
            assistant_message(
                f"The session handed me {len(earlier)} earlier items. You had told me: "
                f'"{said}" Let us pick up from there.'
            )
        ]

    return ScriptedModel([ModelStep.respond(first), ModelStep.respond(second)])


def scripted_clinician_model(note: str, seen: dict) -> ScriptedModel:
    def gather(call):
        return [
            function_call(
                "get_active_medications",
                {"patient_ref": "patient-alvarez"},
                call_id="meds",
            ),
            function_call(
                "get_pharmacy_fills",
                {"patient_ref": "patient-alvarez"},
                call_id="fills",
            ),
            function_call(
                "recall_episodes",
                {"situation": "statin duplicate simvastatin"},
                call_id="past",
            ),
        ]

    def check(call):
        seen.update(tool_outputs(call.input))
        return [
            function_call(
                "search_interactions",
                {"drugs": ["apixaban", "ibuprofen"]},
                call_id="ix",
            )
        ]

    def draft(call):
        seen.update(tool_outputs(call.input))
        return [
            assistant_message(
                json.dumps(
                    {
                        "status": "draft",
                        "patient_ref": "patient-alvarez",
                        "findings": [
                            "Apixaban with ibuprofen raises bleeding risk.",
                            "Single statin is intended. Simvastatin was stopped at the last visit.",
                        ],
                        "note": note,
                    }
                )
            )
        ]

    return ScriptedModel(
        [ModelStep.respond(gather), ModelStep.respond(check), ModelStep.respond(draft)]
    )
