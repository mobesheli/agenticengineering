"""Connect an agent to the finance evidence server over Streamable HTTP.

Start the server in another terminal first:

    python mcp_servers/finance_evidence_server.py

then:

    python -m examples.mcp_connect

Entering the ``async with`` block opens the connection and performs the
handshake. The tool list is fetched when a run starts, so the run lives inside
the block. This script runs the agent against the SDK's scripted model, prints
the tools the model was offered and what the server returned, reads the chart
of accounts resource, and then shows what happens to a run that starts after
the block has closed. With ``OPENAI_API_KEY`` set it also asks the real model a
question through ``run_audit_prep``.
"""

from __future__ import annotations

import asyncio
import os

from agents import Agent, Runner, set_tracing_disabled
from agents.exceptions import UserError
from agents.mcp import MCPServerStreamableHttp
from agents.testing import ScriptedModel, assistant_message, function_call

AUDIT_PREP_INSTRUCTIONS = (
    "You help a control owner prepare audit evidence. Use the evidence server's "
    "tools for every figure; never quote a balance from memory. Entity codes are "
    "four characters such as UK01 and periods look like 2026-Q3."
)

QUESTION = "What is the trial balance for entity UK01 in 2026-Q3 above a 1,000,000 threshold?"


async def run_audit_prep(question: str):
    async with MCPServerStreamableHttp(
        name="finance-evidence",
        params={"url": "http://127.0.0.1:8765/mcp"},
    ) as evidence_server:
        agent = Agent(
            name="audit-prep-assistant",
            instructions=AUDIT_PREP_INSTRUCTIONS,
            mcp_servers=[evidence_server],
        )
        return await Runner.run(agent, input=question)


def scripted_model() -> ScriptedModel:
    """One call to the server's tool, then a one-line answer."""
    return ScriptedModel([
        [function_call("get_trial_balance_snapshot",
                       {"query": {"period": "2026-Q3", "entity": "UK01",
                                  "materiality_threshold": 1_000_000}}, call_id="call_1")],
        [assistant_message("Six accounts sit above the threshold for UK01 in 2026-Q3.")],
    ])


async def demonstrate_lifecycle() -> None:
    model = scripted_model()
    async with MCPServerStreamableHttp(
        name="finance-evidence",
        params={"url": "http://127.0.0.1:8765/mcp"},
    ) as evidence_server:
        print(f"connected  : {evidence_server.name}")
        agent = Agent(
            name="audit-prep-assistant",
            instructions=AUDIT_PREP_INSTRUCTIONS,
            mcp_servers=[evidence_server],
            model=model,
        )
        result = await Runner.run(agent, input=QUESTION)
        offered = [tool.name for tool in model.calls[0].tools]
        print(f"run started: {len(offered)} tool(s) listed for the model: {', '.join(offered)}")
        for item in result.new_items:
            if item.type == "tool_call_output_item":
                text = item.output["text"] if isinstance(item.output, dict) else str(item.output)
                print(f"tool result: {' '.join(text.split())[:110]}...")
        print(f"final      : {result.final_output}")

        contents = await evidence_server.read_resource("schema://accounts")
        first = contents.contents[0].text.splitlines()[:3]
        print("resource   : schema://accounts")
        for line in first:
            print(f"             {line}")

    fresh = scripted_model()
    agent.model = fresh
    try:
        await Runner.run(agent, input=QUESTION)
    except UserError as exc:
        print(f"after block: {str(exc).split('.')[0]}, model calls made: {len(fresh.calls)}")


async def main() -> None:
    set_tracing_disabled(True)
    await demonstrate_lifecycle()
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set; the live question was skipped")
        return
    set_tracing_disabled(False)
    result = await run_audit_prep(QUESTION)
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
