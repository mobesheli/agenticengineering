from __future__ import annotations

import json

from agents import Agent, Runner
from agents.testing import ScriptedModel, assistant_message, function_call

from chapter6.remote import Delegation
from chapter6.sample import BUYER, CASE, bracket_bom
from chapter6.tools import SourcingContext, ask_supplier_for_quote


def test_the_model_sees_only_the_supplier_id():
    schema = ask_supplier_for_quote.params_json_schema
    assert set(schema["properties"]) == {"supplier_id"}


async def test_a_model_led_step_reaches_the_remote_agent_through_the_tool(hood):
    model = ScriptedModel(
        [
            [
                function_call(
                    "ask_supplier_for_quote", {"supplier_id": "nordbolt"}, call_id="q1"
                )
            ],
            [assistant_message("NordBolt quoted 3.13 GBP.")],
        ]
    )
    buyer_agent = Agent(name="sourcing", model=model, tools=[ask_supplier_for_quote])
    deps = SourcingContext(via=Delegation(hood.http, BUYER, CASE), bom=bracket_bom())
    run = await Runner.run(buyer_agent, "Get a quote from NordBolt.", context=deps)
    tool_output = next(
        item
        for item in model.calls[1].input
        if item.get("type") == "function_call_output"
    )
    assert "3.13" in json.dumps(tool_output["output"])
    assert run.final_output == "NordBolt quoted 3.13 GBP."
