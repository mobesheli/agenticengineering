"""The finance evidence server in process, and the lifecycle failures around it."""

import pytest
from agents import Agent, Runner
from agents.exceptions import UserError
from agents.mcp import MCPServerStreamableHttp
from agents.testing import ScriptedModel, assistant_message, function_call

from audit_prep.inprocess import InProcessMCPServer
from mcp_servers import finance_evidence_server as fes

UNUSED_PORT_URL = "http://127.0.0.1:8799/mcp"


async def test_server_exposes_one_tool_and_one_resource():
    tools = await fes.app.list_tools()
    assert [tool.name for tool in tools] == ["get_trial_balance_snapshot"]
    schema = tools[0].input_schema
    query = schema["$defs"]["TrialBalanceQuery"]["properties"]
    assert query["period"]["pattern"] == r"^\d{4}-Q[1-4]$"
    assert query["materiality_threshold"]["minimum"] == 0
    resources = await fes.app.list_resources()
    assert [str(resource.uri) for resource in resources] == ["schema://accounts"]


async def test_server_validates_arguments_before_the_ledger_sees_them():
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError):
        await fes.app.call_tool(
            "get_trial_balance_snapshot",
            {"query": {"period": "Q3-2026", "entity": "UK01", "materiality_threshold": 0}},
        )


async def test_agent_lists_the_tool_when_the_run_starts_inside_the_block():
    model = ScriptedModel([
        [function_call("get_trial_balance_snapshot",
                       {"query": {"period": "2026-Q3", "entity": "UK01",
                                  "materiality_threshold": 1_000_000}}, call_id="call_1")],
        [assistant_message("done")],
    ])
    async with InProcessMCPServer(fes.app) as server:
        agent = Agent(name="a", instructions="x", mcp_servers=[server], model=model)
        result = await Runner.run(agent, "trial balance")
    assert [tool.name for tool in model.calls[0].tools] == ["get_trial_balance_snapshot"]
    output = next(i.output for i in result.new_items if i.type == "tool_call_output_item")
    assert '"source_ref": "tb:UK01:2026-Q3"' in output["text"]


async def test_unavailable_server_fails_before_any_model_call():
    model = ScriptedModel([[assistant_message("never")]])
    with pytest.raises(UserError) as excinfo:
        async with MCPServerStreamableHttp(
            name="finance-evidence", params={"url": UNUSED_PORT_URL}
        ) as server:
            agent = Agent(name="a", instructions="x", mcp_servers=[server], model=model)
            await Runner.run(agent, "hello")
    assert "finance-evidence" in str(excinfo.value)
    assert model.calls == ()


async def test_running_outside_the_block_is_refused_as_not_initialized():
    model = ScriptedModel([[assistant_message("never")]])
    server = MCPServerStreamableHttp(name="finance-evidence", params={"url": UNUSED_PORT_URL})
    agent = Agent(name="a", instructions="x", mcp_servers=[server], model=model)
    with pytest.raises(UserError, match="Server not initialized"):
        await Runner.run(agent, "hello")
    assert model.calls == ()
