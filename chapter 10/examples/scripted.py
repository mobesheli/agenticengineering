"""Scripted model replies, so the examples and tests run without an API key.

The SDK runner, the tools, the guardrails, the approval pause, and the state store
are all real. Only the model's replies are fixed in advance.
"""

from __future__ import annotations

from agents import Agent
from agents.testing import ScriptedModel, assistant_message, function_call
from agents.usage import Usage

from chapter10.bundle import Bundle
from chapter10.contracts import load_contracts
from chapter10.planner import build_planner
from chapter10.platform import Platform

USAGE_PER_TURN = Usage(
    requests=1, input_tokens=900, output_tokens=120, total_tokens=1020
)

ORDER = {
    "asset_id": "P-207",
    "action": "Replace pump bearings",
    "part_number": "BK-6207",
}
PLAN = [
    [function_call("read_sensor_history", {"asset_id": "P-207"}, call_id="call_1")],
    [function_call("get_repair_history", {"asset_id": "P-207"}, call_id="call_2")],
    [function_call("search_parts", {"query": "bearing kit pump"}, call_id="call_3")],
    [function_call("get_lead_time", {"part_number": "BK-6207"}, call_id="call_4")],
    [function_call("create_work_order", ORDER, call_id="call_5")],
]
CLOSING = "{outcome} P-207 is past its alarm limit."
HEALTHY = [
    [function_call("read_sensor_history", {"asset_id": "F-114"}, call_id="call_1")],
    [function_call("get_repair_history", {"asset_id": "F-114"}, call_id="call_2")],
    [assistant_message("F-114 is within its limits. No work order is needed.")],
]
OVERREACH = [
    [function_call("search_parts", {"query": "bearing kit pump"}, call_id="call_1")],
    [
        function_call(
            "create_order", {"part_number": "BK-6207", "quantity": 2}, call_id="call_2"
        )
    ],
    [assistant_message("I found the part. I am not permitted to order it.")],
]


def staging(repo_contracts: str = "template-repository/contracts") -> Platform:
    """A platform with everything switched on, as staging is before a drill."""
    from chapter10.bundle import ROOT

    return Platform(
        contracts=load_contracts(ROOT / repo_contracts),
        endpoints={f"plant-{n}": "maintenance-planner@41.2" for n in range(1, 5)},
        certified={"sensor-history": True, "repair-history": True},
    )


def scripted_planner(
    platform: Platform, bundle: Bundle, session_id: str, turns: list[list]
) -> Agent:
    model = ScriptedModel(turns, default_usage=USAGE_PER_TURN)
    return build_planner(platform, bundle, session_id, model=model)


def closing(outcome: str) -> list[list]:
    return [[assistant_message(CLOSING.format(outcome=outcome))]]
